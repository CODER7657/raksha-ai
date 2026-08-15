"""Reviewer-facing benchmark data (#32 B).

Read-only. Everything here is computed from files already in the repo — the
corpus and the rule engine — so there is no database round trip and no LLM call,
and the numbers cannot drift from what CI enforces.
"""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.services import benchmark, benchmark_llm
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


@router.get("/benchmark/llm")
def llm_benchmark(_user_id: str = Depends(get_current_user)) -> dict:
    """The last committed RAG+LLM run — read from disk, never triggered here.

    Scoring is a CLI (`scripts/run_llm_benchmark.py`) because a run spends
    production's own API quota per case, and a route that scored on demand
    would be a cost amplifier reachable by anyone with a session. This one only
    reads a file, so it is free and idempotent.

    `available: false` rather than a 404 when no run has been committed: the
    dashboard renders the offline half regardless, and an absent benchmark is a
    state to display, not an error to handle.
    """
    report = benchmark_llm.load_report()
    if report is None:
        return {"available": False}

    # What the corpus looks like *now*, so the client can say plainly when the
    # committed run no longer describes it. Computed here rather than trusted
    # from the artifact: the whole point is to detect that the artifact is out
    # of date, so it cannot be the source for both sides of the comparison.
    corpus = benchmark.load_corpus()
    run = report.get("run", {})

    return {
        "available": True,
        **report,
        "currency": {
            "corpus_rows_now": len(corpus),
            "corpus_digest_now": benchmark_llm.corpus_digest(corpus),
            "corpus_rows_at_run": run.get("corpus_rows"),
            "corpus_digest_at_run": run.get("corpus_digest"),
            # `corpus_rows` predates this field on older artifacts, so absence
            # means "unknown", which the UI must not render as "current".
            "stale": (
                run.get("corpus_digest") is None
                or run.get("corpus_digest") != benchmark_llm.corpus_digest(corpus)
            ),
        },
        "provenance": {
            "prompt_version": report.get("run", {}).get("prompt_version"),
            # Observed, not assumed. The provider ladder means a run can be
            # scored partly by Groq and partly by Gemini — the first real run
            # was, because Groq hit its daily token cap partway through — and a
            # reader comparing two runs has to be able to see that.
            "models": report.get("run", {}).get("models", []),
            "measures": "rag_llm_pipeline",
        },
    }
