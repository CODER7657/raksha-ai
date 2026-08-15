"""Reviewer-facing benchmark data (#32 B).

Read-only. Everything here is computed from files already in the repo — the
corpus and the rule engine — so there is no database round trip and no LLM call,
and the numbers cannot drift from what CI enforces.
"""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.services import benchmark
from app.services.llm import GEMINI_MODEL, GROQ_MODEL, PROMPT_VERSION

router = APIRouter(prefix="/api", tags=["benchmark"])


@router.get("/benchmark/offline-rules")
def offline_rule_benchmark(_user_id: str = Depends(get_current_user)) -> dict:
    """Per-language precision and recall for the offline rule engine.

    Authenticated, but not restricted further — there is no role system yet, so
    any signed-in user can read this. That is a real gap for a screen meant to
    be internal: it names which languages have no offline rules, which is a
    map of where the safety net is thinnest. It is consistent with what the
    scan trace already exposes (#18/#19 ship the rule patterns themselves to
    the client), so this widens nothing that was previously closed — but both
    want a reviewer role gate before a pilot.
    """
    report = benchmark.run()

    return {
        **report,
        # Which engine version produced these numbers. Without it a trend line
        # over time is uninterpretable — a jump could be a better rule set or
        # simply a different prompt (ARCHITECTURE.md §03).
        "provenance": {
            "prompt_version": PROMPT_VERSION,
            "primary_model": GROQ_MODEL,
            "fallback_model": GEMINI_MODEL,
            # Named so the dashboard can be explicit that these numbers describe
            # the zero-network fallback, not the RAG+LLM path users normally hit.
            "measures": "offline_rule_engine",
        },
    }
