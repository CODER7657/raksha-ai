"""Assembles the reasoning trace that ships with every verdict.

ARCHITECTURE.md §03: a bank cannot deploy a system whose decisions it cannot
audit. The pipeline already computed all of this — the retrieved patterns were
built into the prompt context and then dropped on the floor, and the offline
rules were reduced to a bare count — so this module is mostly about keeping
evidence that already existed rather than producing anything new.

Two rules govern what goes in the audit payload:

1. **No raw message text.** The scan row already holds the user's own message
   under RLS; repeating it in the audit log widens the blast radius for no
   benefit. The payload carries a SHA-256 of the message instead, which is
   enough to prove a given message produced a given verdict without storing
   the message a second time.
2. **Only what is needed to reproduce the decision** — which rules fired, what
   was retrieved and how similar, and which model and prompt judged it.
"""

import hashlib
import hmac
from typing import Any

from app.services.llm import PROMPT_VERSION, Classification
from app.services.rag import (
    WEAK_MATCH_SIMILARITY,
    RetrievedPattern,
    language_is_covered,
)
from app.services.rule_engine import REVIEW_STATUS, RuleHit


def rule_review(language: str) -> dict[str, Any]:
    """Whether a speaker of this language has read its detection rules.

    Exposed per verdict because a user is entitled to know how much to trust the
    one in front of them, and `REVIEW_STATUS` currently reaches only the
    benchmark payload — which no user sees.

    The distinction that matters, and the reason this is not a single boolean:
    every language falls back to the **English** rules, which are reviewed. So a
    code-mixed message ("your KYC is expiring, share OTP") is caught by reviewed
    rules in all twelve languages. What is unreviewed is detection of text
    written wholly in the language's own script. Reporting that as "this
    language is unchecked" would overstate the gap as badly as saying nothing
    understates it.
    """
    status = REVIEW_STATUS.get(language, "unreviewed")
    return {
        "status": status,
        # True when the native-script rules have been read by a speaker.
        "native_reviewed": status == "in-service",
        # Always true: the English rules run for every language and are
        # reviewed, so code-mixed and English-content messages are covered
        # everywhere.
        "code_mixed_reviewed": True,
        # `inherited` is its own claim — mr borrows Hindi's rules because the
        # vocabulary genuinely overlaps, which is weaker than review and
        # stronger than nothing.
        "inherited_from": "hi" if status == "inherited" else None,
    }


def build_trace(
    hits: list[RuleHit],
    patterns: list[RetrievedPattern],
    classification: Classification | None,
    language: str = "en",
) -> dict[str, Any]:
    """The trace as the frontend consumes it. `classification` is None on the
    degraded path, where the offline rules alone produced the verdict and
    there is no model to stamp."""
    trace: dict[str, Any] = {
        "rule_review": rule_review(language),
        "offline_rules_fired": [
            {
                "rule_id": hit.rule_id,
                "pattern": hit.pattern,
                "matched_text": hit.matched_text,
            }
            for hit in hits
        ],
        "retrieved_patterns": [
            {
                "pattern_text": pattern.pattern_text,
                "category": pattern.category,
                "similarity": round(pattern.similarity, 4),
                # #32 C/E: a reviewer, and eventually an auditor, must be able
                # to tell which evidence behind a verdict was machine-drafted.
                # Carried per pattern rather than as a summary flag, because
                # "one of five patterns came from an agent" and "all five did"
                # are different claims about how much to trust the verdict.
                "provenance": pattern.provenance,
                "drafted_by": pattern.drafted_by,
            }
            for pattern in patterns
        ],
        # Whether retrieval had anything to retrieve *from* (#88).
        #
        # An empty `retrieved_patterns` has meant two different things and said
        # neither: "the corpus was searched and nothing was close" versus "this
        # language has no corpus". The first is a weak signal about the message.
        # The second is a statement about us — nine of the twelve supported
        # languages have zero patterns — and it is the one that decides whether
        # the verdict was grounded at all.
        #
        # In the trace rather than inferred by the reader, because the reader
        # would have to know that `match_scam_patterns` applies no similarity
        # floor in order to draw it, and that is not a fact a UI should have to
        # know about a SQL function.
        "retrieval": {
            "language_covered": language_is_covered(patterns),
            "patterns_retrieved": len(patterns),
            # How many actually reached the prompt. Distinct from the count
            # above and not derivable from it: five retrieved of which none
            # cleared the weak-match floor is a different verdict from five
            # retrieved and five used, and `retrieved_patterns` lists both
            # kinds without saying which was which.
            "patterns_used": sum(
                1 for p in patterns if p.similarity > WEAK_MATCH_SIMILARITY
            ),
        },
    }

    if classification is not None:
        trace["model"] = {
            "provider": classification.provider,
            "model": classification.model,
            "prompt_version": classification.prompt_version,
        }

    return trace


def build_trace_from_cache(
    hits: list[RuleHit],
    provider: str,
    model: str,
    cached_at: str | None,
    language: str = "en",
) -> dict[str, Any]:
    """The trace for a verdict served from the cache (#48).

    Two things are deliberately different from `build_trace`.

    `retrieved_patterns` is empty, and honestly so: a cache hit skips retrieval,
    so there were no patterns. Replaying the ones stored with the original
    verdict would be inventing evidence for a step that did not run.

    `retrieval.language_covered` is `None` for the same reason, and that is a
    third state rather than a `False`. Retrieval did not run, so whether this
    language has patterns was never established — reporting `False` would
    assert the #88 gap on a scan that never looked, which is the same class of
    error as replaying the patterns.

    `model.cached` says the verdict was reused. Without it the audit record
    would credit a model call that never happened, and two identical verdicts
    would be indistinguishable from two independent judgements — which is
    exactly the sort of thing an auditor is entitled to be able to tell apart.

    The offline rules still run on every scan, so their hits are real and
    current rather than replayed.
    """
    return {
        # Reported on the cached path too. The rules still ran on this scan —
        # only the classification was reused — so how much a speaker has checked
        # them is exactly as relevant as on a fresh verdict.
        "rule_review": rule_review(language),
        "offline_rules_fired": [
            {
                "rule_id": hit.rule_id,
                "pattern": hit.pattern,
                "matched_text": hit.matched_text,
            }
            for hit in hits
        ],
        "retrieved_patterns": [],
        "retrieval": {
            # Not False. Retrieval never ran, so this was never established.
            "language_covered": None,
            "patterns_retrieved": 0,
            "patterns_used": 0,
            "skipped": "cache_hit",
        },
        "model": {
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "cached": True,
            "first_judged_at": cached_at,
        },
    }


def _normalise(text: str) -> str:
    """Trivial variants of the same forwarded SMS must land on the same digest."""
    return text.strip().lower()


def hash_text(text: str) -> str:
    """Unkeyed digest, used by the community counter.

    Deliberately not peppered: `community_reports` is keyed on this value and
    every row written so far used the unkeyed form, so changing it would orphan
    the existing counts. The aggregate table holds no user linkage, which is
    what makes that acceptable here and not in the audit log."""
    return hashlib.sha256(_normalise(text).encode()).hexdigest()


def audit_digest(text: str) -> str:
    """Digest for the audit payload, which *is* linked to a user_id.

    Keyed with a server-held pepper when one is configured. A bare SHA-256 is
    reversible for anything low-entropy — a phone number is ~10^10 guesses, an
    OTP 10^6 — so "we only store a hash" would not be a true statement about a
    record that also names the user who scanned it (ARCHITECTURE.md §07).

    With no pepper set this degrades to the unkeyed digest rather than
    refusing to run: a missing operational secret must not stop a fraud warning
    from being issued. The payload records which form was used, so a reader can
    tell a keyed digest from an unkeyed one instead of assuming."""
    from app.core.config import get_settings

    pepper = get_settings().audit_hash_pepper
    if not pepper:
        return hashlib.sha256(_normalise(text).encode()).hexdigest()
    return hmac.new(pepper.encode(), _normalise(text).encode(), hashlib.sha256).hexdigest()


def digest_is_keyed() -> bool:
    from app.core.config import get_settings

    return bool(get_settings().audit_hash_pepper)


def build_audit_payload(
    *,
    input_hash: str,
    language: str,
    input_type: str,
    verdict: str,
    risk_score: int,
    trace: dict[str, Any],
) -> dict[str, Any]:
    """What gets hashed into the chain. Deliberately narrower than `trace` —
    the rule *pattern* and the full retrieved `pattern_text` are useful to a
    reader but are reproducible from the code and the pattern table, so the
    record keeps only the identifiers and the scores."""
    return {
        "input_digest": input_hash,
        # Named so a reader can tell a peppered digest from a bare SHA-256
        # instead of inferring it from deployment config that may have changed.
        "input_digest_keyed": digest_is_keyed(),
        "language": language,
        "input_type": input_type,
        "verdict": verdict,
        "risk_score": risk_score,
        "rules_fired": [rule["rule_id"] for rule in trace.get("offline_rules_fired", [])],
        "retrieved": [
            {
                "category": pattern["category"],
                "similarity": pattern["similarity"],
                # In the hash-chained record, not only the response. "Was this
                # verdict influenced by an agent?" is a question an auditor asks
                # months later, about a decision nobody remembers — and by then
                # the pattern row may have been edited or deleted. Only the
                # audit entry can answer it, and only if it was written down at
                # the time.
                "provenance": pattern.get("provenance", "human"),
            }
            for pattern in trace.get("retrieved_patterns", [])
        ],
        # Whether there was a corpus to ground this verdict in at all (#88).
        #
        # Belongs in the chain for the same reason `agent_influenced` does. "Was
        # this decision grounded in retrieved evidence, or did the model answer
        # unaided?" is a question a regulator can ask about a six-month-old
        # verdict, and by then the corpus will have grown — nine languages are
        # empty today and the intention is that they will not stay that way.
        # Reconstructing it later from the pattern table would give the wrong
        # answer, confidently.
        #
        # None where retrieval did not run (a cache hit), preserved rather than
        # flattened to False, because "not established" and "no corpus" are
        # different facts about the same absent evidence.
        "retrieval_language_covered": trace.get("retrieval", {}).get("language_covered"),
        # A single flag so the question is answerable without walking the list.
        "agent_influenced": any(
            pattern.get("provenance") == "agent"
            for pattern in trace.get("retrieved_patterns", [])
        ),
        "model": trace.get("model"),
    }


# The chain hash is deliberately NOT computed here.
#
# It is tempting to mirror the database's hashing in Python so the chain can be
# checked without a round trip. Doing so would be wrong: Postgres orders `jsonb`
# keys by length first and then bytewise, whereas `json.dumps(sort_keys=True)`
# is purely lexicographic. The two disagree the moment a payload holds keys like
# "language" (8 chars) and "verdict" (7) — Postgres emits "verdict" first,
# Python emits "language" first, and the digests diverge for identical data.
#
# A verifier that disagrees with the chain it verifies is worse than no verifier,
# so hashing and verification both live in SQL, next to the data:
# `append_verdict_audit()` and `verify_verdict_chain()` in
# supabase/migrations/0004_traceability.sql.
