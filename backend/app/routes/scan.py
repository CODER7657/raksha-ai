import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.supabase_client import get_supabase
from app.rate_limit import limiter
from app.services import llm, rag, stt
from app.services import trace as trace_service
from app.services.rule_engine import offline_rule_hits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scan"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB — plenty for a short call snippet, caps abuse
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg",
}


class ScanTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
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


def _run_scan_pipeline(text: str, language: str, input_type: str, user_id: str) -> dict:
    """Shared by both /scan/text and /scan/audio once we have plain text in
    hand — same RAG retrieval + LLM classification + offline fallback +
    persistence for either input type."""
    hits = offline_rule_hits(text, language)

    patterns = rag.retrieve_similar_patterns(text, language)
    context_block = rag.format_context_block(patterns)

    classification: llm.Classification | None = None
    try:
        classification = llm.classify_message(text, language, context_block)
        result = classification.result
    except Exception:
        if hits:
            result = {
                "risk_score": 70,
                "verdict": "suspicious",
                "flagged_phrases": [hit.matched_text for hit in hits],
                "explanation": "AI service unavailable — flagged by offline pattern rules as a precaution.",
                "recommended_action": "Do not share OTP/personal details. Verify with the official app/helpline before acting.",
            }
        else:
            raise HTTPException(status_code=503, detail="Detection service temporarily unavailable")

    trace = trace_service.build_trace(hits, patterns, classification)
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
    # trace legitimately has none — the audit record cannot exist until the scan
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
        raise HTTPException(status_code=413, detail="Audio file too large (10MB limit)")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcript = stt.transcribe(
        audio_bytes,
        language,
        filename=file.filename or "audio.webm",
        content_type=base_content_type,
    )
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
