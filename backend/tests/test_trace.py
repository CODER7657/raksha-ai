"""What ends up in a trace, and — more importantly — what must not."""

from app.services import trace as trace_service
from app.services.llm import Classification
from app.services.rag import RetrievedPattern
from app.services.rule_engine import RuleHit

HITS = [RuleHit(rule_id="otp_share", pattern=r"\bOTP\b", matched_text="share your OTP")]
PATTERNS = [
    RetrievedPattern(pattern_text="Your KYC is expiring", category="kyc_scam", similarity=0.80951234),
    RetrievedPattern(pattern_text="You have won a prize", category="lottery", similarity=0.31),
]
CLASSIFICATION = Classification(
    result={"verdict": "high_risk", "risk_score": 95},
    provider="groq",
    model="llama-3.3-70b-versatile",
)

MESSAGE = "Dear customer, share your OTP now"


def test_trace_itemises_rules_rather_than_counting_them():
    trace = trace_service.build_trace(HITS, PATTERNS, CLASSIFICATION)
    assert trace["offline_rules_fired"] == [
        {"rule_id": "otp_share", "pattern": r"\bOTP\b", "matched_text": "share your OTP"}
    ]


def test_trace_keeps_retrieved_patterns_that_used_to_be_discarded():
    trace = trace_service.build_trace(HITS, PATTERNS, CLASSIFICATION)
    assert [p["category"] for p in trace["retrieved_patterns"]] == ["kyc_scam", "lottery"]
    # Rounded so a float's last bits cannot change a hash for identical input.
    assert trace["retrieved_patterns"][0]["similarity"] == 0.8095


def test_trace_stamps_the_model_and_prompt_version():
    trace = trace_service.build_trace(HITS, PATTERNS, CLASSIFICATION)
    assert trace["model"] == {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "prompt_version": "scan-v1",
    }


def test_degraded_path_has_no_model_stamp():
    """When both providers are down the offline rules produce the verdict, so
    there is no model to name. Recording one anyway would be a lie in the
    audit log."""
    trace = trace_service.build_trace(HITS, PATTERNS, None)
    assert "model" not in trace
    assert trace["offline_rules_fired"]


def test_trace_never_carries_the_message_itself():
    """`matched_text` is a fragment the rule tripped on, which is the point.
    The whole message must not appear anywhere in the trace."""
    trace = trace_service.build_trace(HITS, PATTERNS, CLASSIFICATION)
    assert MESSAGE not in str(trace)


# --- Audit payload ---------------------------------------------------------

def build_payload() -> dict:
    trace = trace_service.build_trace(HITS, PATTERNS, CLASSIFICATION)
    return trace_service.build_audit_payload(
        input_hash=trace_service.audit_digest(MESSAGE),
        language="en",
        input_type="text",
        verdict="high_risk",
        risk_score=95,
        trace=trace,
    )


def test_audit_payload_holds_a_digest_not_the_message():
    payload = build_payload()
    assert MESSAGE not in str(payload)
    assert payload["input_digest"] == trace_service.audit_digest(MESSAGE)
    assert len(payload["input_digest"]) == 64


def test_audit_payload_drops_pattern_text_but_keeps_the_scores():
    """Pattern text is reproducible from the pattern table, so the record keeps
    only what cannot be recovered: which category matched and how closely."""
    payload = build_payload()
    assert "Your KYC is expiring" not in str(payload)
    # `provenance` joined this in #32 E. It belongs in the record for the
    # opposite reason `pattern_text` does not: the text is reproducible from the
    # pattern table, whereas whether a pattern was machine-drafted is exactly
    # what a later edit or deletion would destroy.
    assert payload["retrieved"] == [
        {"category": "kyc_scam", "similarity": 0.8095, "provenance": "human"},
        {"category": "lottery", "similarity": 0.31, "provenance": "human"},
    ]


def test_audit_payload_records_which_rules_fired():
    assert build_payload()["rules_fired"] == ["otp_share"]


def test_hash_text_is_stable_across_case_and_padding():
    """The community counter keys on this digest, so trivial variants of the
    same forwarded SMS have to land on the same row."""
    assert trace_service.hash_text("  Share Your OTP  ") == trace_service.hash_text("share your otp")


def test_hash_text_separates_different_messages():
    assert trace_service.hash_text("share your OTP") != trace_service.hash_text("share your PIN")


# --- Digest keying (ARCHITECTURE.md §07) -----------------------------------

def test_audit_digest_is_keyed_when_a_pepper_is_configured(monkeypatch):
    """With a pepper set, the audit digest must not equal the bare SHA-256 —
    otherwise a short message (a phone number, an OTP) is brute-forceable from
    a record that also names the user who scanned it."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AUDIT_HASH_PEPPER", "test-pepper")
    try:
        keyed = trace_service.audit_digest("9876543210")
        assert trace_service.digest_is_keyed()
        assert keyed != trace_service.hash_text("9876543210")
        assert len(keyed) == 64
    finally:
        get_settings.cache_clear()


def test_audit_digest_degrades_rather_than_refusing(monkeypatch):
    """A missing operational secret must not stop a fraud warning being
    issued, so an unset pepper falls back to the unkeyed digest."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AUDIT_HASH_PEPPER", "")
    try:
        assert not trace_service.digest_is_keyed()
        assert trace_service.audit_digest("hello") == trace_service.hash_text("hello")
    finally:
        get_settings.cache_clear()


def test_payload_records_whether_the_digest_was_keyed():
    """A reader must be able to tell the two apart from the record itself."""
    assert "input_digest_keyed" in build_payload()


def test_community_digest_stays_unkeyed(monkeypatch):
    """community_reports is keyed on hash_text; peppering it would orphan every
    count written so far."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AUDIT_HASH_PEPPER", "test-pepper")
    try:
        import hashlib

        assert trace_service.hash_text("Share your OTP") == hashlib.sha256(
            b"share your otp"
        ).hexdigest()
    finally:
        get_settings.cache_clear()


def test_python_does_not_reimplement_the_chain_hash():
    """Guards the note in trace.py: Postgres and Python order jsonb keys
    differently, so a second implementation here would silently disagree with
    the chain it claims to verify. Hashing lives in SQL."""
    assert not hasattr(trace_service, "compute_chain_hash")
    assert not hasattr(trace_service, "canonical_json")
