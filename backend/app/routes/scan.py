import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.supabase_client import get_supabase
from app.rate_limit import limiter
from app.services import (
    domain_age,
    email_signals,
    link_signals,
    llm,
    rag,
    safe_actions,
    stt,
    threat_feeds,
    verdict_cache,
)
from app.services import trace as trace_service
from app.services.rule_engine import offline_rule_hits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scan"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # 4MB: under the host's 4.5MB request cap; minutes of compressed speech
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg",
}


class ScanTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: LanguageCode = "en"


class ScanEmailRequest(BaseModel):
    # Five times the SMS cap. An email carries quoted history, a signature block
    # and a client's forwarded header block on top of the message itself, and
    # 4000 characters would truncate ordinary mail — cutting the body is how the
    # link that matters gets dropped before anything looks at it.
    text: str = Field(min_length=1, max_length=20000)
    language: LanguageCode = "en"


class ScanResult(BaseModel):
    risk_score: int
    verdict: str
    flagged_phrases: list[str]
    explanation: str
    recommended_action: str
    community_report_count: int
    offline_flags_matched: int
    transcript: str | None = None
    # The reasoning trace (ARCHITECTURE.md §03). Optional in the schema because
    # the audit sub-record is best-effort — see `_append_audit_record`.
    trace: dict | None = None


def _report_to_community_radar(text: str, language: str) -> int:
    """Anonymized aggregate counter — we hash the message, never store raw text here."""
    # Same digest the audit payload uses, so a community count and an audit
    # record can be correlated to the same message without either holding it.
    pattern_hash = trace_service.hash_text(text)
    supabase = get_supabase()
    response = supabase.rpc(
        "increment_community_report",
        {"p_pattern_hash": pattern_hash, "p_language": language},
    ).execute()
    return response.data if isinstance(response.data, int) else 1


def _append_audit_record(
    scan_id: str | None, user_id: str, payload: dict
) -> dict | None:
    """Best-effort append to the hash-chained log.

    Deliberately non-fatal. A user in front of a live scam gets their verdict
    even if the audit write fails; the alternative is withholding a fraud
    warning because a compliance record could not be written, which inverts
    what this product is for. The failure is loud in the logs, and the missing
    record is visible in the response as an absent `trace.audit` rather than
    being papered over."""
    try:
        response = get_supabase().rpc(
            "append_verdict_audit",
            {"p_scan_id": scan_id, "p_user_id": user_id, "p_payload": payload},
        ).execute()
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        return {
            "record_id": str(row["id"]),
            "hash": row["hash"],
            "prev_hash": row["prev_hash"],
        }
    except Exception:
        logger.exception("Audit chain append failed for scan %s", scan_id)
        return None


def _degraded_verdict(hits: list) -> dict:
    """The verdict when no model answered — either the providers are down or we
    refused what one of them said.

    Its action comes from the same closed table the classifier now chooses from
    (#113), so there is exactly one place user-facing advice is written. A second
    copy here is how the two would eventually disagree about what we tell people.
    """
    action_id, action_text = safe_actions.resolve_action(safe_actions.FALLBACK_ACTION)
    return {
        "risk_score": 70,
        "verdict": "suspicious",
        "flagged_phrases": [hit.matched_text for hit in hits],
        "explanation": "AI service unavailable — flagged by offline pattern rules as a precaution.",
        "recommended_action_id": action_id,
        "recommended_action": action_text,
    }


def _link_signals_for(text: str) -> list:
    """A2 stage 1 over every link in the message.

    Deterministic, local, and measured at well under a millisecond per URL
    (`test_link_signals_latency.py`), so it runs on both the cached and the live
    path rather than only where a model call was already being made.

    Failure is swallowed on purpose. These signals add evidence to a verdict;
    they are not the verdict, and a user in front of a live scam must not lose
    their warning because a link check raised.
    """
    try:
        signals = []
        for url in link_signals.extract_urls(text):
            signals.extend(link_signals.evaluate(url))
            signals.extend(threat_feeds.signals_for(url))
            signals.extend(domain_age.signals_for(url))
        return signals
    except Exception:
        logger.warning("Link signal evaluation failed; verdict unaffected", exc_info=True)
        return []


def _run_scan_pipeline(
    text: str,
    language: str,
    input_type: str,
    user_id: str,
    extra_trace: dict | None = None,
) -> dict:
    """Shared by both /scan/text and /scan/audio once we have plain text in
    hand — same RAG retrieval + LLM classification + offline fallback +
    persistence for either input type."""
    hits = offline_rule_hits(text, language)
    digest = trace_service.hash_text(text)

    # Ask the cache before spending anything. A scam campaign sends one message
    # to thousands of people, and judging it once is the difference between a
    # burst of traffic costing 1 classification and costing 1,000 — which is how
    # a rate limit becomes a user with no warning (#48).
    #
    # Retrieval is skipped on a hit as well. It is the cheaper call, but it is
    # still a call, and the patterns are only ever used to build the prompt for
    # the classification we are not making.
    # Computed before the cache branch so a cached verdict carries the same
    # evidence as a fresh one. The verdict is cached; the link checks are not,
    # and they are cheap enough to redo — a domain's reputation can change
    # between two scans of one viral message, and serving week-old link evidence
    # under a cached verdict would be the same class of error as replaying
    # retrieval (#48).
    addenda: dict = dict(extra_trace or {})
    link_block = trace_service.link_signal_block(_link_signals_for(text))
    if link_block:
        addenda["link_signals"] = link_block

    cached = verdict_cache.lookup(digest, language)
    if cached is not None:
        result = cached["result"]
        trace = trace_service.build_trace_from_cache(
            hits, cached["provider"], cached["model"], cached["cached_at"], language
        )
        return _persist_and_respond(
            text=text,
            language=language,
            input_type=input_type,
            user_id=user_id,
            result=result,
            trace={**trace, **addenda},
            hits=hits,
        )

    patterns = rag.retrieve_similar_patterns(text, language)
    context_block = rag.format_context_block(patterns)

    classification: llm.Classification | None = None
    try:
        classification = llm.classify_message(text, language, context_block)
        result = classification.result
    except safe_actions.UnsafeOutput:
        # The model was steered into writing something we will not repeat (#113).
        #
        # Handled with the provider failures below rather than separately, and
        # that is the point: an attacker who successfully injects must not
        # thereby deny the user their warning. The offline rules already fired on
        # this text, so the fall-through produces a real conservative verdict
        # rather than an error page.
        #
        # Logged apart from a provider outage, because "both providers failed"
        # and "someone attacked the classifier" want different responses and
        # #45 is the standing lesson about collapsing two causes into one line.
        logger.warning(
            "Rejected classifier output as unsafe; falling back to offline rules",
            exc_info=True,
        )
        classification = None
        result = _degraded_verdict(hits)
    except Exception:
        if hits:
            result = _degraded_verdict(hits)
        else:
            raise HTTPException(status_code=503, detail="Detection service temporarily unavailable")

    trace = trace_service.build_trace(hits, patterns, classification, language)
    verdict_cache.store(digest, language, result, classification)

    return _persist_and_respond(
        text=text,
        language=language,
        input_type=input_type,
        user_id=user_id,
        result=result,
        trace={**trace, **addenda},
        hits=hits,
    )


def _apply_link_floor(result: dict, trace: dict) -> tuple[dict, dict]:
    """Stop a `safe` verdict sitting on top of evidence that says otherwise.

    A floor, not an override — see `trace.link_floor_reason`. It only ever
    raises caution, never lowers it, and it leaves `suspicious` and `high_risk`
    untouched.

    Applied on the cached path as readily as the live one, which is what makes
    fresh link evidence under a stale verdict safe rather than contradictory: a
    domain blocklisted since the message was first judged can now only make that
    verdict more cautious.
    """
    reason = trace_service.link_floor_reason(trace.get("link_signals"))
    if not reason or result["verdict"] != "safe":
        return result, trace

    # `do_not_click_link`, not FALLBACK_ACTION. The fallback is
    # `do_not_share_credentials` — the most conservative action, which is right
    # when we do not know *why* we are worried. Here we know precisely why, and
    # pairing "the link did not look ordinary" with "do not share your OTP"
    # gives a user an explanation about a link and advice about credentials.
    action_id, action_text = safe_actions.resolve_action("do_not_click_link")
    raised = {
        **result,
        "verdict": "suspicious",
        # Not 70. The offline-rule fallback uses 70 for "a rule fired and no
        # model answered"; this is "a model answered safe and the link says
        # otherwise", which is a weaker claim and should not read as the same
        # confidence.
        "risk_score": max(result.get("risk_score", 0), 60),
        "explanation": (
            "The message text looked ordinary, but the link in it did not — "
            "see the link checks below."
        ),
        "recommended_action_id": action_id,
        "recommended_action": action_text,
    }
    floored_trace = {
        **trace,
        "link_signals": {**trace["link_signals"], "verdict_floor_applied": True},
    }
    logger.info("Link evidence floored a safe verdict (%s)", reason)
    return raised, floored_trace


def _persist_and_respond(
    *,
    text: str,
    language: str,
    input_type: str,
    user_id: str,
    result: dict,
    trace: dict,
    hits: list,
) -> dict:
    """Everything after a verdict exists, shared by the cached and live paths.

    Extracted so a cache hit takes exactly the same route through persistence
    and the audit chain as a fresh classification. A second copy of this would
    eventually diverge, and the way it would diverge is by forgetting to write
    an audit record for the cheap path - which is the one that will run most
    often once a campaign is circulating.
    """
    # Before persistence and before the audit record, so what is stored and what
    # is signed are the verdict the user was actually shown. Flooring after the
    # audit append would put a different verdict in the compliance log than in
    # the response, which is the one place they must not differ.
    result, trace = _apply_link_floor(result, trace)

    community_count = _report_to_community_radar(text, language)

    supabase = get_supabase()
    inserted = (
        supabase.table("scans")
        .insert(
            {
                "user_id": user_id,
                "input_type": input_type,
                "input_text": text,
                "language": language,
                "risk_score": result["risk_score"],
                "verdict": result["verdict"],
                "flagged_phrases": result["flagged_phrases"],
                "explanation": result["explanation"],
                "recommended_action": result["recommended_action"],
                "trace": trace,
            }
        )
        .execute()
    )
    scan_rows = inserted.data or []
    scan_id = scan_rows[0]["id"] if scan_rows else None

    audit = _append_audit_record(
        scan_id,
        user_id,
        trace_service.build_audit_payload(
            input_hash=trace_service.audit_digest(text),
            language=language,
            input_type=input_type,
            verdict=result["verdict"],
            risk_score=result["risk_score"],
            trace=trace,
        ),
    )
    # A new dict rather than mutating `trace` in place: the copy already handed
    # to the scans insert must not grow an `audit` key afterwards. The stored
    # trace legitimately has none - the audit record cannot exist until the scan
    # row it points at does, and the link is navigable the other way via
    # verdict_audit.scan_id.
    response_trace = {**trace, "audit": audit} if audit else trace

    return {
        **result,
        "community_report_count": community_count,
        "offline_flags_matched": len(hits),
        "trace": response_trace,
    }

@router.post("/scan/text", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
def scan_text(
    request: Request,
    payload: ScanTextRequest,
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    result = _run_scan_pipeline(payload.text, payload.language, "text", user_id)
    return ScanResult(**result)


@router.post("/scan/email", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
def scan_email(
    request: Request,
    payload: ScanEmailRequest,
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    """A shared email. #115 §2, plan §01b.

    Email is mostly a **delivery** question rather than a detection one — the
    dangerous part is the link, and A2 stage 1 already reads links. What this
    route adds is a sender, and the honest handling of one.

    The body is classified rather than the whole paste. A mail client's quoted
    header block is metadata, and leaving it in would run the scam rules over
    `Date:` and `To:` lines and report them to a user as content.

    **The sender is almost never verifiable here**, and the response says so
    rather than staying quiet about it. Share-to-app delivers `text/plain`; SPF
    needs the connecting IP and DKIM needs raw bytes that sharing rewrites. That
    caveat reaches the user through `trace.sender` and never reaches the signal
    count — being unable to check a sender is not evidence against them, and
    treating it as evidence would bias every forwarded email toward a block.
    """
    parsed = email_signals.parse(payload.text)
    assessment = email_signals.evaluate(payload.text)

    result = _run_scan_pipeline(
        parsed.body or payload.text,
        payload.language,
        "email",
        user_id,
        extra_trace={
            "sender": trace_service.sender_block(
                assessment.sender_verification, assessment.caveats
            )
        },
    )
    return ScanResult(**result)


@router.post("/scan/audio", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
async def scan_audio(
    request: Request,
    file: UploadFile,
    language: LanguageCode = "en",
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    # Browser-recorded audio (MediaRecorder) sends a content-type with codec
    # params, e.g. "audio/webm;codecs=opus" — compare on the base MIME type only.
    base_content_type = (file.content_type or "").split(";", 1)[0].strip()
    if base_content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {file.content_type}")

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (4MB limit)")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        transcript = stt.transcribe(
            audio_bytes,
            language,
            filename=file.filename or "audio.webm",
            content_type=base_content_type,
        )
    except stt.STTUnavailable as exc:
        logger.warning("speech-to-text unavailable: %s", exc.reason)
        raise HTTPException(
            status_code=503,
            detail="Voice scanning is unavailable right now. Please type or paste the message instead.",
        ) from exc
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe any speech from the audio")

    result = _run_scan_pipeline(transcript, language, "audio", user_id)
    return ScanResult(**result, transcript=transcript)


@router.get("/history")
def get_history(user_id: str = Depends(get_current_user)) -> list[dict]:
    supabase = get_supabase()
    response = (
        supabase.table("scans")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []
