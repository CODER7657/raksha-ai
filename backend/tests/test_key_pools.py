"""Batch work must not spend the quota a live scan needs.

On 15 August a red-team run made ~30 calls in a burst, rate-limited Groq, and —
with the Gemini fallback dead at the time — took live detection down with it.
Three faults lined up, but only one of them is architectural: an internal tool
was drawing on the same key as the product it exists to improve.

This file pins the fix. It is mostly a discipline problem, and discipline is
what tests are for: the assertions that matter are the ones checking the agent
modules *default* to batch, because nothing else stops someone pointing a loop
at production traffic at 2am.
"""

import pytest

from app.core.config import get_settings
from app.services import benchmark_llm, llm, redteam


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def set_keys(monkeypatch, **values):
    for name in (
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY_BATCH",
        "GEMINI_API_KEY_BATCH",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def test_pools_resolve_to_their_own_keys(monkeypatch):
    set_keys(
        monkeypatch,
        GROQ_API_KEY="live-groq",
        GEMINI_API_KEY="live-gemini",
        GROQ_API_KEY_BATCH="batch-groq",
        GEMINI_API_KEY_BATCH="batch-gemini",
    )
    assert llm.keys_for(llm.INTERACTIVE) == ("live-groq", "live-gemini")
    assert llm.keys_for(llm.BATCH) == ("batch-groq", "batch-gemini")


def test_batch_falls_back_to_interactive_with_a_warning(monkeypatch, caplog):
    """A fresh clone with one key should still be able to run the benchmark.
    It should just say what quota it is about to spend."""
    set_keys(monkeypatch, GROQ_API_KEY="live-groq", GEMINI_API_KEY="live-gemini")

    with caplog.at_level("WARNING", logger="app.services.llm"):
        assert llm.keys_for(llm.BATCH) == ("live-groq", "live-gemini")

    assert any("batch" in record.message.lower() for record in caplog.records), (
        "falling back to the interactive pool must not be silent — that is the "
        "exact situation that caused the outage"
    )


def test_a_partial_batch_pool_fills_the_gap_from_interactive(monkeypatch):
    """One batch key set and not the other is a likely half-configured state.
    It should work rather than fail, using the interactive key for the rung
    that has none."""
    set_keys(
        monkeypatch,
        GROQ_API_KEY="live-groq",
        GEMINI_API_KEY="live-gemini",
        GROQ_API_KEY_BATCH="batch-groq",
    )
    assert llm.keys_for(llm.BATCH) == ("batch-groq", "live-gemini")


def test_interactive_never_borrows_batch_keys(monkeypatch):
    """The fallback is one-directional on purpose. A scan reaching for the
    batch pool would be the outage in reverse — user traffic quietly spending
    an agent's quota and failing when a nightly loop exhausts it."""
    set_keys(monkeypatch, GROQ_API_KEY_BATCH="batch-groq", GEMINI_API_KEY_BATCH="batch-gemini")
    assert llm.keys_for(llm.INTERACTIVE) == ("", "")


# --- the assertions that actually prevent a repeat ------------------------


def test_the_red_team_loop_uses_the_batch_pool(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(
        redteam.llm,
        "complete",
        lambda system, user, pool=llm.INTERACTIVE: seen.append(pool)
        or type("C", (), {"text": '{"variants": []}', "provider": "g", "model": "m"})(),
    )
    redteam.generate_variants(
        {"id": "x", "language": "en", "text": "Share your OTP"}, "paraphrase", 1
    )
    assert seen == [llm.BATCH], f"generator called on {seen}, expected batch"


def test_the_judge_uses_the_batch_pool(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(
        redteam.llm,
        "complete",
        lambda system, user, pool=llm.INTERACTIVE: seen.append(pool)
        or type(
            "C",
            (),
            {"text": '{"still_same_scam": true}', "provider": "g", "model": "m"},
        )(),
    )
    redteam.judge_preservation("original", "variant")
    assert seen == [llm.BATCH]


def test_the_benchmark_classifies_on_the_batch_pool(monkeypatch):
    seen: list[str] = []

    def fake_classify(text, language, context, pool=llm.INTERACTIVE):
        seen.append(pool)
        return type(
            "C",
            (),
            {
                "result": {"verdict": "safe", "risk_score": 1},
                "provider": "groq",
                "model": llm.GROQ_MODEL,
                "prompt_version": llm.PROMPT_VERSION,
            },
        )()

    monkeypatch.setattr(benchmark_llm.llm, "classify_message", fake_classify)
    monkeypatch.setattr(
        benchmark_llm.rag, "retrieve_similar_patterns", lambda *a, **k: []
    )
    monkeypatch.setattr(benchmark_llm.rag, "format_context_block", lambda p: "")

    benchmark_llm.classify_case(
        {"id": "x", "language": "en", "text": "Share your OTP", "label": "scam"}, {}
    )
    assert seen == [llm.BATCH], f"benchmark classified on {seen}, expected batch"


def test_both_agents_retrieve_on_the_batch_pool(monkeypatch):
    """Retrieval embeds, and embedding costs quota too — a benchmark run embeds
    every case whether or not its verdict is cached."""
    seen: list[str | None] = []

    def fake_retrieve(text, language, top_k=5, pool=None):
        seen.append(pool)
        return []

    monkeypatch.setattr(benchmark_llm.rag, "retrieve_similar_patterns", fake_retrieve)
    monkeypatch.setattr(benchmark_llm.rag, "format_context_block", lambda p: "")
    monkeypatch.setattr(
        benchmark_llm.llm,
        "classify_message",
        lambda t, l, c, pool=None: type(
            "C",
            (),
            {
                "result": {"verdict": "safe", "risk_score": 1},
                "provider": "groq",
                "model": llm.GROQ_MODEL,
                "prompt_version": llm.PROMPT_VERSION,
            },
        )(),
    )
    benchmark_llm.classify_case(
        {"id": "x", "language": "en", "text": "t", "label": "scam"}, {}
    )

    monkeypatch.setattr(redteam.rag, "retrieve_similar_patterns", fake_retrieve)
    monkeypatch.setattr(redteam.rag, "format_context_block", lambda p: "")
    monkeypatch.setattr(redteam, "offline_rule_hits", lambda t, l: [])
    monkeypatch.setattr(
        redteam.llm,
        "classify_message",
        lambda t, l, c, pool=None: type(
            "C", (), {"result": {"verdict": "safe", "risk_score": 1}}
        )(),
    )
    redteam.detect_full("t", "en")

    assert seen == [llm.BATCH, llm.BATCH], f"retrieval pools were {seen}"


# --- retries belong to batch alone ----------------------------------------


def test_interactive_gets_one_attempt_and_no_backoff(monkeypatch):
    """A scan has a person waiting, often mid-scam. Falling to the next provider
    immediately beats making them sit through a backoff, so the interactive pool
    must never sleep."""
    monkeypatch.setattr(llm, "_call_groq", _raise("429 rate limit"))
    monkeypatch.setattr(llm, "_call_gemini", _raise("429 rate limit"))
    monkeypatch.setattr(llm.time, "sleep", _forbidden_sleep)

    with pytest.raises(RuntimeError, match="Both Groq and Gemini failed"):
        llm.complete("s", "u", llm.INTERACTIVE)


def test_batch_retries_a_rate_limit(monkeypatch):
    """The loop lost ~30 already-paid-for calls by dying on a 429."""
    attempts = {"n": 0}
    slept: list[float] = []

    def flaky(system, user, pool=llm.INTERACTIVE):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("429 rate limit reached")
        return "recovered"

    monkeypatch.setattr(llm, "_call_groq", flaky)
    monkeypatch.setattr(llm, "_call_gemini", _raise("429 rate limit"))
    monkeypatch.setattr(llm.time, "sleep", slept.append)

    result = llm.complete("s", "u", llm.BATCH)
    assert result.text == "recovered"
    assert slept, "batch retries must back off rather than hammer"


def test_batch_does_not_retry_a_dead_model(monkeypatch):
    """Retrying only helps a rate limit. A 404 fails identically three times,
    and sleeping through it just makes the error slower to arrive."""
    calls = {"n": 0}

    def dead(system, user, pool=llm.INTERACTIVE):
        calls["n"] += 1
        raise RuntimeError("404 model not found")

    monkeypatch.setattr(llm, "_call_groq", dead)
    monkeypatch.setattr(llm, "_call_gemini", dead)
    monkeypatch.setattr(llm.time, "sleep", _forbidden_sleep)

    with pytest.raises(RuntimeError, match="Both Groq and Gemini failed"):
        llm.complete("s", "u", llm.BATCH)
    assert calls["n"] == 2, "one attempt per rung, no retry on a dead model"


def _raise(message):
    def _fn(*args, **kwargs):
        raise RuntimeError(message)

    return _fn


def _forbidden_sleep(seconds):
    raise AssertionError(f"slept {seconds}s on a path that must not back off")
