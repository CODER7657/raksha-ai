"""The scan pipeline end to end, with Supabase and the LLM stubbed.

The cases that matter here are the failure paths: what a user gets when the
LLM is down, and whether a broken audit log can take a fraud warning with it.
"""

import pytest
from fastapi import HTTPException

from app.routes import scan
from app.services.llm import Classification
from app.services.rag import RetrievedPattern

SCAM = "Dear customer, your KYC is expiring today. Share your OTP now or your account will be blocked."
BENIGN = "Your order has been shipped and will arrive on Tuesday"

GOOD_RESULT = {
    "risk_score": 95,
    "verdict": "high_risk",
    "flagged_phrases": ["Share your OTP now"],
    "explanation": "Asks for an OTP.",
    "recommended_action": "Do not share it.",
}


class FakeTable:
    def __init__(self, sink: dict):
        self._sink = sink

    def insert(self, row):
        self._sink["scan_row"] = row
        return self

    def execute(self):
        return type("R", (), {"data": [{"id": "scan-uuid-1"}]})()


class FakeSupabase:
    def __init__(self, sink: dict, audit_ok: bool = True):
        self._sink = sink
        self._audit_ok = audit_ok

    def table(self, _name):
        return FakeTable(self._sink)

    def rpc(self, name, params):
        self._sink.setdefault("rpc", []).append((name, params))
        if name == "append_verdict_audit" and not self._audit_ok:
            raise RuntimeError("audit table unreachable")
        payload = (
            [{"id": 7, "hash": "h" * 64, "prev_hash": "g" * 64}]
            if name == "append_verdict_audit"
            else 3
        )
        return type("R", (), {"data": payload, "execute": lambda s: s})()

    def execute(self):
        return self


@pytest.fixture
def sink(monkeypatch):
    """Wires the pipeline to fakes and hands back what it tried to write."""
    data: dict = {}

    def install(audit_ok: bool = True):
        fake = FakeSupabase(data, audit_ok=audit_ok)

        class Rpc:
            def __init__(self, name, params):
                self.name, self.params = name, params

            def execute(self):
                return fake.rpc(self.name, self.params)

        fake_client = type(
            "C",
            (),
            {
                "table": lambda s, n: FakeTable(data),
                "rpc": lambda s, n, p: Rpc(n, p),
            },
        )()
        monkeypatch.setattr(scan, "get_supabase", lambda: fake_client)
        monkeypatch.setattr(scan.trace_service, "get_supabase", lambda: fake_client, raising=False)
        monkeypatch.setattr(
            scan.rag,
            "retrieve_similar_patterns",
            lambda t, l: [RetrievedPattern("Your KYC is expiring", "kyc_scam", 0.81)],
        )
        return data

    data["install"] = install
    return install


def classify_ok(*_args, **_kwargs):
    return Classification(result=dict(GOOD_RESULT), provider="groq", model="llama-3.3-70b-versatile")


def classify_down(*_args, **_kwargs):
    raise RuntimeError("Both Groq and Gemini failed")


def test_happy_path_returns_a_full_trace(monkeypatch, sink):
    written = sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_ok)

    out = scan._run_scan_pipeline(SCAM, "en", "text", "user-1")

    trace = out["trace"]
    assert {r["rule_id"] for r in trace["offline_rules_fired"]} >= {"otp_share", "kyc_expiry"}
    assert trace["retrieved_patterns"][0]["category"] == "kyc_scam"
    assert trace["model"]["provider"] == "groq"
    assert trace["audit"]["hash"] == "h" * 64
    # The persisted trace must not have grown an audit key by aliasing the
    # object the response returns.
    assert "audit" not in written["scan_row"]["trace"]
    assert written["scan_row"]["trace"] == {k: v for k, v in trace.items() if k != "audit"}


def test_offline_rule_count_still_matches_the_itemised_list(monkeypatch, sink):
    """The frontend falls back to this count when the list is absent, so the
    two must not drift apart."""
    sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_ok)

    out = scan._run_scan_pipeline(SCAM, "en", "text", "user-1")
    assert out["offline_flags_matched"] == len(out["trace"]["offline_rules_fired"])


def test_llm_down_but_rules_fire_still_warns_the_user(monkeypatch, sink):
    """Fail safe, never confidently wrong. Before the rule-engine fix this
    message matched nothing, so this path raised 503 on a real scam."""
    sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_down)

    out = scan._run_scan_pipeline(SCAM, "en", "text", "user-1")

    assert out["verdict"] == "suspicious"
    assert out["risk_score"] == 70
    assert out["trace"]["offline_rules_fired"]
    # No model judged this, so nothing may claim to have.
    assert "model" not in out["trace"]


def test_llm_down_and_nothing_fires_refuses_rather_than_clearing(monkeypatch, sink):
    """A benign-looking message with no evidence must not come back "safe" —
    wrongly clearing a scam is the one unrecoverable failure."""
    sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_down)

    with pytest.raises(HTTPException) as excinfo:
        scan._run_scan_pipeline(BENIGN, "en", "text", "user-1")
    assert excinfo.value.status_code == 503


def test_a_failed_audit_write_does_not_withhold_the_verdict(monkeypatch, sink):
    """A user with a scammer on the phone gets their warning even if the
    compliance record cannot be written."""
    written = sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_ok)
    monkeypatch.setattr(scan, "_append_audit_record", lambda *a, **k: None)

    out = scan._run_scan_pipeline(SCAM, "en", "text", "user-1")

    assert out["verdict"] == "high_risk"
    # Absent rather than faked, so the gap is visible in the response.
    assert "audit" not in out["trace"]
    assert written["scan_row"]["verdict"] == "high_risk"


def test_audit_payload_sent_to_the_chain_excludes_the_message(monkeypatch, sink):
    written = sink()
    monkeypatch.setattr(scan.llm, "classify_message", classify_ok)

    scan._run_scan_pipeline(SCAM, "en", "text", "user-1")

    appends = [p for name, p in written["rpc"] if name == "append_verdict_audit"]
    assert appends, "no audit append attempted"
    payload = appends[0]["p_payload"]
    assert SCAM not in str(payload)
    assert len(payload["input_digest"]) == 64
    assert payload["verdict"] == "high_risk"
