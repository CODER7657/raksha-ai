"""The email route, and link evidence reaching the trace at all. #115 §2.

`test_scan_pipeline.py` covers the pipeline's failure paths. This covers what
§2 adds on top: that a shared email is classified on its body rather than on a
mail client's quoted headers, that what could not be established about the
sender reaches the user, and — the one that matters most — that it reaches the
user *without* reaching the count that decides blocking.

Stage 1's signals were built in #120 and deliberately not wired to a route
there; this is where they arrive.
"""

import pytest

from app.routes import scan
from app.services.llm import Classification
from app.services.rag import RetrievedPattern

PHISH_EMAIL = """\
---------- Forwarded message ---------
From: HDFC Bank <alerts@hdfcbank.com>
Date: Sat, 16 Aug 2026 at 10:22
Subject: Your account will be blocked
To: <user@example.com>

Dear Customer, your KYC is pending. Verify at http://hdfc-verify.info/kyc
"""

RESULT = {
    "risk_score": 90,
    "verdict": "high_risk",
    "flagged_phrases": ["KYC is pending"],
    "explanation": "Asks the reader to visit a lookalike domain.",
    "recommended_action": "Do not open the link.",
}


@pytest.fixture
def wired(monkeypatch):
    """Supabase, retrieval and the model stubbed; the real signal code runs."""
    written: dict = {}

    class Table:
        def insert(self, row):
            written["scan_row"] = row
            return self

        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "scan-1"}]})()

    class Rpc:
        def __init__(self, name):
            self.name = name

        def execute(self):
            payload = (
                [{"id": 1, "hash": "h" * 64, "prev_hash": None}]
                if self.name == "append_verdict_audit"
                else 2
            )
            return type("R", (), {"data": payload})()

    client = type("C", (), {"table": lambda s, n: Table(), "rpc": lambda s, n, p: Rpc(n)})()

    monkeypatch.setattr(scan, "get_supabase", lambda: client)
    monkeypatch.setattr(scan.trace_service, "get_supabase", lambda: client, raising=False)
    monkeypatch.setattr(
        scan.rag, "retrieve_similar_patterns", lambda t, lang: [
            RetrievedPattern("KYC expiring", "kyc_scam", 0.8)
        ]
    )
    monkeypatch.setattr(
        scan.llm,
        "classify_message",
        lambda *a, **k: Classification(result=dict(RESULT), provider="groq", model="llama"),
    )
    monkeypatch.setattr(scan.verdict_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(scan.verdict_cache, "store", lambda *a, **k: True)
    # The cache table for domain age does not exist in tests, and the hot path
    # is required to survive that — see test_domain_age.
    monkeypatch.setattr(scan.domain_age, "signals_for", lambda url: [])
    return written


def _email_trace(wired) -> dict:
    """What `scan_email` assembles, without standing up the HTTP layer."""
    parsed = scan.email_signals.parse(PHISH_EMAIL)
    assessment = scan.email_signals.evaluate(PHISH_EMAIL)
    out = scan._run_scan_pipeline(
        parsed.body,
        "en",
        "email",
        "user-1",
        extra_trace={
            "sender": scan.trace_service.sender_block(
                assessment.sender_verification, assessment.caveats
            )
        },
    )
    return out["trace"]


# --- link evidence reaches the trace --------------------------------------


def test_link_signals_appear_in_the_trace(wired):
    trace = _email_trace(wired)
    assert "link_signals" in trace
    assert "brand_impersonation" in {s["name"] for s in trace["link_signals"]["signals"]}


def test_the_trace_carries_the_witness_count_rather_than_the_signal_count(wired):
    """Left for the reader to derive, a UI would count signals and report "three
    checks agree" about one observation. Carried so it cannot."""
    block = _email_trace(wired)["link_signals"]
    assert block["independent_witnesses"] <= len(block["signals"])
    assert block["independent_witnesses"] == len({s["basis"] for s in block["signals"]})


def test_a_message_with_no_link_omits_the_block_entirely(wired):
    """Absent, not empty. An empty object reads as "the links were checked and
    were fine", which is a claim about a message that had none."""
    out = scan._run_scan_pipeline("Share your OTP right now", "en", "text", "user-1")
    assert "link_signals" not in out["trace"]


def test_an_ordinary_sms_with_a_link_gets_the_same_evidence(wired):
    """Not email-only. #120 shipped the checks and wired them nowhere; SMS is
    the channel that matters most and it goes through the same path."""
    out = scan._run_scan_pipeline(
        "URGENT: verify at http://hdfc-verify.info/kyc", "en", "text", "user-1"
    )
    assert "link_signals" in out["trace"]


# --- the sender, and what cannot be said about it -------------------------


def test_the_unverifiable_sender_reaches_the_user(wired):
    sender = _email_trace(wired)["sender"]
    assert sender["verification"] == "unverifiable"
    assert sender["caveats"]


def test_the_caveat_never_becomes_a_countable_witness(wired):
    """The tightest constraint in this file, and the reason `sender` is a
    separate trace field rather than another signal.

    If "we could not verify the sender" counted, every forwarded email would
    carry a free witness toward being blocked — absence of evidence promoted
    into evidence, on this feature's most common input.
    """
    trace = _email_trace(wired)
    bases = {s["basis"] for s in trace["link_signals"]["signals"]}
    assert "sender_auth" not in bases
    assert trace["link_signals"]["independent_witnesses"] == len(bases)


def test_the_body_is_classified_rather_than_the_quoted_headers(wired):
    """A client's forwarded block is metadata. Classifying it would run the scam
    rules over `Date:` and `To:` lines and report them to a user as content."""
    scan._run_scan_pipeline(scan.email_signals.parse(PHISH_EMAIL).body, "en", "email", "user-1")
    stored = wired["scan_row"]["input_text"]
    assert "Dear Customer" in stored
    assert "Subject:" not in stored
    assert "Forwarded message" not in stored


def test_email_is_recorded_as_its_own_channel(wired):
    """Migration 0011. Filed as `text`, email's precision would be averaged into
    SMS's and neither number would mean anything — and every accuracy claim on
    this project is reported per-slice."""
    scan._run_scan_pipeline("body with no link", "en", "email", "user-1")
    assert wired["scan_row"]["input_type"] == "email"


# --- failure must not cost a warning --------------------------------------


def test_a_broken_link_check_does_not_take_the_verdict_with_it(wired, monkeypatch):
    """These signals add evidence to a verdict; they are not the verdict. A user
    in front of a live scam keeps their warning."""
    monkeypatch.setattr(
        scan.link_signals, "extract_urls", lambda text: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    out = scan._run_scan_pipeline("verify at http://hdfc-verify.info/kyc", "en", "text", "user-1")
    assert out["verdict"] == "high_risk"
    assert "link_signals" not in out["trace"]
