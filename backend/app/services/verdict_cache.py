"""Verdicts for messages we have already judged.

A scam campaign sends one message to thousands of people. Without this, each of
those costs an embedding and a classification for a message already judged —
against free-tier keys shared with everything else, which is how a burst of
traffic becomes a rate limit becomes a user with no warning (#48).

Keyed on the same digest `community_reports` already uses, so a message has one
identity across the system rather than two.

## Three things this deliberately does not do

**It does not cache the degraded path.** When both providers are down,
`scan.py` falls back to the offline rules and returns a conservative verdict.
Storing that would mean serving "AI service unavailable" as a considered
judgement for a week after the outage ended — a worse answer than the one we
would have computed, presented as though it were better.

**It does not hide that a verdict was cached.** The trace says so, so the audit
record cannot credit a model call that never happened, and a reviewer comparing
two identical verdicts can tell whether they were reached twice or once.

**It does not fail a scan.** Every operation is best-effort: a cache that is
unreachable, slow or wrong costs money, never a fraud warning. Same posture as
the audit append in #18, for the same reason.

## What it stores

The verdict and its explanation, not the message. The digest is one-way, and
this table holds no user id — unlike `verdict_audit`, which is why that one is
peppered (#39, ARCHITECTURE §07) and this one does not need to be.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.supabase_client import get_supabase
from app.services import llm

logger = logging.getLogger(__name__)

#: How long a verdict stays usable. Generous, because `prompt_version` already
#: invalidates on any change that could move a verdict — this bound exists for
#: the things a version bump cannot express: the model's own drift, and a scam
#: pattern table that has grown since.
MAX_AGE = timedelta(days=7)

TABLE = "verdict_cache"


def _fresh(created_at: str | None) -> bool:
    if not created_at:
        return False
    try:
        stamped = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - stamped <= MAX_AGE


def lookup(digest: str, language: str) -> dict[str, Any] | None:
    """A previous verdict for this exact message, or None.

    None on any failure, including an unreachable database — the caller then
    does what it would have done anyway, which is classify the message.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("*")
            .eq("digest", digest)
            .eq("language", language)
            .eq("prompt_version", llm.PROMPT_VERSION)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.warning("Verdict cache lookup failed; classifying instead", exc_info=True)
        return None

    rows = response.data or []
    if not rows:
        return None

    row = rows[0]
    if not _fresh(row.get("created_at")):
        return None

    try:
        get_supabase().rpc(
            "touch_verdict_cache",
            {
                "p_digest": digest,
                "p_language": language,
                "p_prompt_version": llm.PROMPT_VERSION,
            },
        ).execute()
    except Exception:
        # Hit counting is telemetry. Losing it must not lose the hit.
        logger.debug("Could not record a verdict cache hit", exc_info=True)

    return {
        "result": {
            "verdict": row["verdict"],
            "risk_score": row["risk_score"],
            "flagged_phrases": row["flagged_phrases"],
            "explanation": row["explanation"],
            "recommended_action": row["recommended_action"],
        },
        "provider": row["provider"],
        "model": row["model"],
        "cached_at": row.get("created_at"),
    }


def store(
    digest: str,
    language: str,
    result: dict[str, Any],
    classification: llm.Classification | None,
) -> bool:
    """Remember a verdict. Returns whether it was stored.

    `classification is None` means the offline rules produced this verdict
    because both providers were down. That is never cached — see the module
    docstring. The signature takes the classification rather than a boolean so a
    caller cannot accidentally assert a model was involved when none was.
    """
    if classification is None:
        return False

    try:
        get_supabase().table(TABLE).upsert(
            {
                "digest": digest,
                "language": language,
                "prompt_version": classification.prompt_version,
                "verdict": result["verdict"],
                "risk_score": result["risk_score"],
                "flagged_phrases": result["flagged_phrases"],
                "explanation": result["explanation"],
                "recommended_action": result["recommended_action"],
                "provider": classification.provider,
                "model": classification.model,
            },
            on_conflict="digest,language,prompt_version",
        ).execute()
    except Exception:
        logger.warning("Could not store a verdict in the cache", exc_info=True)
        return False
    return True
