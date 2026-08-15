"""The verdict cache, and the three things it must never do.

Saving money is the easy half and not what these tests are for. What matters is
that a cache hit is indistinguishable from a fresh classification *to the user*
and completely distinguishable *to an auditor*, and that the one verdict which
must never be reused never is.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import llm, verdict_cache
from app.services import trace as trace_service
from app.services.rule_engine import RuleHit


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, _):
        return self

    def upsert(self, row, **kwargs):
        self._sink["upserted"] = row
        return self

    def execute(self):
        return FakeResponse(self._rows)


class FakeSupabase:
    def __init__(self, rows=None, sink=None, fail=False):
        self._rows = rows or []
        self._sink = sink if sink is not None else {}
        self._fail = fail

    def table(self, _name):
        if self._fail:
            raise RuntimeError("database unreachable")
        return FakeTable(self._rows, self._sink)

    def rpc(self, name, params):
        self._sink.setdefault("rpc", []).append(name)
        return FakeResponse(None)


def row(**overrides):
    base = {
        "digest": "abc",
        "language": "en",
        "prompt_version": llm.PROMPT_VERSION,
        "verdict": "high_risk",
        "risk_score": 92,
        "flagged_phrases": ["share your OTP"],
        "explanation": "Asks for an OTP.",
        "recommended_action": "Do not share it.",
        "provider": "groq",
        "model": llm.GROQ_MODEL,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {**base, **overrides}


def classification():
    return llm.Classification(
        result={"verdict": "high_risk", "risk_score": 92},
        provider="groq",
        model=llm.GROQ_MODEL,
    )


@pytest.fixture
def supabase(monkeypatch):
    def _install(fake):
        monkeypatch.setattr(verdict_cache, "get_supabase", lambda: fake)
        return fake

    return _install


# --- the verdict that must never be reused --------------------------------


def test_the_degraded_verdict_is_never_cached(supabase):
    """When both providers are down, `scan.py` returns a conservative verdict
    from the offline rules. Caching it would serve "AI service unavailable" as a
    considered judgement for a week after the outage ended."""
    sink = {}
    supabase(FakeSupabase(sink=sink))

    stored = verdict_cache.store(
        "abc", "en", {"verdict": "suspicious", "risk_score": 70}, classification=None
    )

    assert stored is False
    assert "upserted" not in sink, "nothing may be written for a degraded verdict"


def test_a_real_verdict_is_cached(supabase):
    sink = {}
    supabase(FakeSupabase(sink=sink))
    result = {
        "verdict": "high_risk",
        "risk_score": 92,
        "flagged_phrases": ["x"],
        "explanation": "e",
        "recommended_action": "a",
    }

    assert verdict_cache.store("abc", "en", result, classification()) is True
    assert sink["upserted"]["digest"] == "abc"
    assert sink["upserted"]["prompt_version"] == llm.PROMPT_VERSION


# --- never costing a scan --------------------------------------------------


def test_an_unreachable_cache_returns_none_rather_than_raising(supabase):
    """A cache that is down costs money, never a fraud warning. The caller then
    does what it would have done anyway: classify the message."""
    supabase(FakeSupabase(fail=True))
    assert verdict_cache.lookup("abc", "en") is None


def test_a_failed_store_does_not_raise(supabase):
    supabase(FakeSupabase(fail=True))
    assert verdict_cache.store("abc", "en", {"verdict": "safe"}, classification()) is False


def test_a_hit_counter_failure_does_not_lose_the_hit(monkeypatch, supabase):
    """Hit counting is telemetry. Losing it must not lose the verdict."""

    class RpcFails(FakeSupabase):
        def rpc(self, name, params):
            raise RuntimeError("rpc unavailable")

    supabase(RpcFails(rows=[row()]))
    assert verdict_cache.lookup("abc", "en") is not None


# --- freshness -------------------------------------------------------------


def test_a_stale_verdict_is_not_served(supabase):
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    supabase(FakeSupabase(rows=[row(created_at=old)]))
    assert verdict_cache.lookup("abc", "en") is None


def test_a_verdict_inside_the_window_is_served(supabase):
    recent = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    supabase(FakeSupabase(rows=[row(created_at=recent)]))
    assert verdict_cache.lookup("abc", "en") is not None


def test_an_unparseable_timestamp_is_treated_as_stale(supabase):
    """Fail toward spending money rather than toward serving something we
    cannot date."""
    supabase(FakeSupabase(rows=[row(created_at="not a date")]))
    assert verdict_cache.lookup("abc", "en") is None


def test_a_miss_returns_none(supabase):
    supabase(FakeSupabase(rows=[]))
    assert verdict_cache.lookup("abc", "en") is None


# --- the trace has to tell the truth ---------------------------------------


def test_a_cached_trace_says_it_was_cached():
    """Otherwise the audit record credits a model call that never happened, and
    two identical verdicts are indistinguishable from two judgements."""
    hits = [RuleHit(rule_id="otp_share", pattern="p", matched_text="share your OTP")]
    trace = trace_service.build_trace_from_cache(
        hits, "groq", llm.GROQ_MODEL, "2026-08-15T10:00:00+00:00"
    )

    assert trace["model"]["cached"] is True
    assert trace["model"]["first_judged_at"] == "2026-08-15T10:00:00+00:00"
    assert trace["model"]["provider"] == "groq"


def test_a_cached_trace_claims_no_retrieved_patterns():
    """A hit skips retrieval, so there were none. Replaying the ones stored with
    the original verdict would be inventing evidence for a step that did not
    run."""
    trace = trace_service.build_trace_from_cache([], "groq", llm.GROQ_MODEL, None)
    assert trace["retrieved_patterns"] == []


def test_a_cached_trace_still_reports_live_rule_hits():
    """The offline rules run on every scan regardless, so their hits are current
    rather than replayed — and they are what the user sees named in the UI."""
    hits = [RuleHit(rule_id="kyc_expiry", pattern="p", matched_text="KYC expiring")]
    trace = trace_service.build_trace_from_cache(hits, "groq", llm.GROQ_MODEL, None)

    assert [h["rule_id"] for h in trace["offline_rules_fired"]] == ["kyc_expiry"]


def test_a_live_trace_does_not_claim_to_be_cached():
    """The two builders must stay distinguishable, or the flag means nothing."""
    trace = trace_service.build_trace([], [], classification())
    assert "cached" not in trace["model"]
