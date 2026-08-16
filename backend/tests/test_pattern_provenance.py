"""Agent provenance on the evidence behind a verdict (#32 C/E).

AGENT-LAYER.md §03: a generated scam approved as a pattern is the poisoning
path the review gate exists to prevent. If that gate is ever bypassed, the only
way to find out which verdicts were affected is a record of which patterns
arrived that way — and that record cannot be reconstructed later.
"""

from app.services import trace as trace_service
from app.services.llm import Classification
from app.services.rag import RetrievedPattern

CLASSIFICATION = Classification(
    result={"verdict": "high_risk", "risk_score": 95},
    provider="groq",
    model="llama-3.3-70b-versatile",
)


def test_an_unstated_provenance_defaults_to_human_not_agent():
    """Overstating agent involvement is the failure that matters here: #32 C
    exists to report that number honestly, and a default of 'agent' would
    inflate it for every hand-written row."""
    pattern = RetrievedPattern("Share the OTP", "otp_scam", 0.9)
    assert pattern.provenance == "human"
    assert pattern.drafted_by is None


def test_the_trace_carries_provenance_per_pattern():
    """Per pattern, not as one flag. "One of five came from an agent" and "all
    five did" are different claims about how much of the verdict rests on
    machine-drafted evidence."""
    patterns = [
        RetrievedPattern("Hand written", "otp_scam", 0.9),
        RetrievedPattern("Drafted", "kyc_scam", 0.8, provenance="agent", drafted_by="a1_discovery"),
    ]
    trace = trace_service.build_trace([], patterns, CLASSIFICATION)

    assert [p["provenance"] for p in trace["retrieved_patterns"]] == ["human", "agent"]
    assert trace["retrieved_patterns"][1]["drafted_by"] == "a1_discovery"


def test_the_audit_payload_records_agent_influence():
    """In the hash-chained record, not only the response. Months later the
    pattern row may have been edited or deleted, and only the audit entry can
    still answer "was this verdict influenced by an agent?"."""
    patterns = [
        RetrievedPattern("Drafted", "kyc_scam", 0.8, provenance="agent", drafted_by="a1_discovery")
    ]
    trace = trace_service.build_trace([], patterns, CLASSIFICATION)
    payload = trace_service.build_audit_payload(
        input_hash="x" * 64,
        language="en",
        input_type="text",
        verdict="high_risk",
        risk_score=95,
        trace=trace,
    )

    assert payload["agent_influenced"] is True
    assert payload["retrieved"][0]["provenance"] == "agent"


def test_a_verdict_with_no_agent_evidence_says_so():
    trace = trace_service.build_trace(
        [], [RetrievedPattern("Hand written", "otp_scam", 0.9)], CLASSIFICATION
    )
    payload = trace_service.build_audit_payload(
        input_hash="x" * 64,
        language="en",
        input_type="text",
        verdict="high_risk",
        risk_score=95,
        trace=trace,
    )
    assert payload["agent_influenced"] is False


def test_a_cached_verdict_claims_no_agent_influence():
    """A cache hit skips retrieval, so there were no patterns — and claiming
    agent influence for evidence that was never fetched would be as wrong as
    replaying the patterns themselves."""
    trace = trace_service.build_trace_from_cache([], "groq", "llama-3.3-70b-versatile", None)
    payload = trace_service.build_audit_payload(
        input_hash="x" * 64,
        language="en",
        input_type="text",
        verdict="high_risk",
        risk_score=95,
        trace=trace,
    )
    assert payload["agent_influenced"] is False
    assert payload["retrieved"] == []


def test_an_old_trace_without_provenance_is_read_as_human_not_crashed():
    """Traces written before this column existed have no provenance. The audit
    payload builder must still work on them — an auditor reading an old record
    needs it to open, not to raise."""
    old_trace = {
        "offline_rules_fired": [],
        "retrieved_patterns": [{"category": "otp_scam", "similarity": 0.9}],
    }
    payload = trace_service.build_audit_payload(
        input_hash="x" * 64,
        language="en",
        input_type="text",
        verdict="high_risk",
        risk_score=95,
        trace=old_trace,
    )
    assert payload["agent_influenced"] is False
    assert payload["retrieved"][0]["provenance"] == "human"


def test_the_migration_forbids_an_unapproved_agent_pattern():
    """The guarantee is the database constraint, not the application. Asserted
    on the migration text so removing it is a visible edit rather than a
    silently weaker gate."""
    import pathlib

    sql = (
        pathlib.Path(__file__).resolve().parents[2]
        / "supabase/migrations/0007_pattern_provenance.sql"
    ).read_text(encoding="utf-8")

    assert "scam_patterns_agent_rows_need_approval" in sql
    assert "approved_by is not null" in sql
    # The function must be dropped before recreation — `create or replace`
    # cannot change a return type, and without the drop the migration fails
    # halfway with the columns already added.
    assert "drop function if exists public.match_scam_patterns" in sql


# --- what `code_mixed_reviewed` actually rests on (#101 review) -------------


def test_every_language_falls_back_to_the_english_rules():
    """`trace.rule_review.code_mixed_reviewed` is derived from the English
    rules being reviewed. That inference also needs the English rules to
    actually *run* for every language — which lives in `offline_rule_hits`, not
    in `trace.py`, so deriving alone cannot catch its removal.

    If the fallback is ever dropped, this fails and whoever dropped it has to
    decide what the trace should now tell a Tamil user, rather than the payload
    quietly continuing to promise cover that is gone.
    """
    from app.services.rule_engine import REVIEW_STATUS, offline_rule_hits

    english_content = "Your KYC is expiring. Please share OTP or your account will be blocked."

    for language in REVIEW_STATUS:
        fired = {hit.rule_id for hit in offline_rule_hits(english_content, language)}
        assert fired, (
            f"English-content message fired nothing in '{language}'. The English "
            f"fallback in offline_rule_hits has been removed or narrowed, so "
            f"trace.rule_review.code_mixed_reviewed is now claiming cover that "
            f"does not exist."
        )


def test_code_mixed_cover_is_derived_from_english_being_reviewed(monkeypatch):
    """Not a constant. Were English ever to stop being reviewed, the claim has
    to stop with it."""
    from app.services import trace as trace_service

    assert trace_service.rule_review("ta")["code_mixed_reviewed"] is True

    monkeypatch.setitem(trace_service.REVIEW_STATUS, "en", "unreviewed")
    assert trace_service.rule_review("ta")["code_mixed_reviewed"] is False
