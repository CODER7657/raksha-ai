"""The LLM benchmark, with retrieval and classification stubbed.

Nothing here touches a network or spends quota — the point of these tests is the
scoring arithmetic, the cache contract, and the leakage guard, none of which
need a real model. A test that called the real classifier would be slow, flaky,
and would bill the same free-tier key production runs on.
"""

import pytest

from app.services import benchmark_llm, llm
from app.services.rag import RetrievedPattern


def case(id_, language="en", label="scam", text="Share your OTP now", **extra):
    return {"id": id_, "language": language, "label": label, "text": text, **extra}


class FakeClassification:
    def __init__(self, verdict, risk_score, model=None):
        self.result = {"verdict": verdict, "risk_score": risk_score}
        self.provider = "groq"
        self.model = model or llm.GROQ_MODEL
        self.prompt_version = llm.PROMPT_VERSION


@pytest.fixture
def stubbed(monkeypatch):
    """Retrieval returns one weak match; classification says high_risk."""
    calls = {"classify": 0, "retrieve": 0}

    def fake_retrieve(text, language, top_k=5, pool=None):
        calls["retrieve"] += 1
        return [RetrievedPattern(pattern_text="unrelated", category="kyc_scam", similarity=0.4)]

    def fake_classify(text, language, context, pool=None):
        calls["classify"] += 1
        return FakeClassification("high_risk", 90)

    monkeypatch.setattr(benchmark_llm.rag, "retrieve_similar_patterns", fake_retrieve)
    monkeypatch.setattr(benchmark_llm.rag, "format_context_block", lambda p: "")
    monkeypatch.setattr(benchmark_llm.llm, "classify_message", fake_classify)
    return calls


def test_dry_run_spends_nothing(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a"), case("b")])
    result = benchmark_llm.run(confirm_cost=False, cache_path=tmp_path / "c.json")

    assert result["dry_run"] is True
    assert result["estimate"]["classification_calls"] == 2
    assert stubbed["classify"] == 0, "a dry run must not call the model"
    assert stubbed["retrieve"] == 0, "a dry run must not embed either"


def test_scoring_arithmetic(monkeypatch, tmp_path, stubbed):
    """One true positive, one false positive: the classifier says high_risk to
    everything, so the benign case is scored against it."""
    monkeypatch.setattr(
        benchmark_llm,
        "load_corpus",
        lambda path=None: [case("scam-1"), case("benign-1", label="benign", text="Order shipped")],
    )
    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")

    english = next(lang for lang in result["languages"] if lang["language"] == "en")
    assert (english["true_positives"], english["false_positives"]) == (1, 1)
    assert english["precision"] == 0.5
    assert english["recall"] == 1.0


def test_missed_scam_is_itemised(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(
        benchmark_llm.llm,
        "classify_message",
        lambda text, language, context, pool=None: FakeClassification("safe", 5),
    )
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("missed-1")])
    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")

    english = next(lang for lang in result["languages"] if lang["language"] == "en")
    assert english["false_negatives"] == 1
    assert english["recall"] == 0.0
    assert english["missed_cases"][0]["id"] == "missed-1"


def test_cache_prevents_a_second_call(monkeypatch, tmp_path, stubbed):
    cache_path = tmp_path / "c.json"
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a")])

    benchmark_llm.run(confirm_cost=True, cache_path=cache_path)
    assert stubbed["classify"] == 1

    second = benchmark_llm.run(confirm_cost=True, cache_path=cache_path)
    assert stubbed["classify"] == 1, "second run must be free"
    assert second["run"]["cache_hits"] == 1


def test_prompt_version_change_invalidates_cache(monkeypatch, tmp_path, stubbed):
    """A verdict produced by a different prompt measures a system we no longer
    ship, so it must not be reused."""
    cache_path = tmp_path / "c.json"
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a")])

    benchmark_llm.run(confirm_cost=True, cache_path=cache_path)
    assert stubbed["classify"] == 1

    # Derived, not a literal. This previously said "scan-v2", which silently
    # became a no-op the day PROMPT_VERSION was bumped to scan-v2 — the test
    # then asserted that not changing the version invalidates the cache, and
    # failed for a reason unrelated to what it checks.
    monkeypatch.setattr(
        benchmark_llm.llm, "PROMPT_VERSION", f"{llm.PROMPT_VERSION}-changed"
    )
    benchmark_llm.run(confirm_cost=True, cache_path=cache_path)
    assert stubbed["classify"] == 2, "a new prompt version must re-score"


def test_unknown_model_in_cache_is_not_trusted(tmp_path):
    assert benchmark_llm._usable(
        {"prompt_version": llm.PROMPT_VERSION, "model": llm.GROQ_MODEL}
    )
    assert not benchmark_llm._usable(
        {"prompt_version": llm.PROMPT_VERSION, "model": "llama-2-retired"}
    )


def test_leaked_case_is_excluded_and_reported(monkeypatch, tmp_path, stubbed):
    """A corpus case that is effectively present in the pattern table would be
    graded against the system's own notes, so it is excluded from the figures
    and named in the report."""
    monkeypatch.setattr(
        benchmark_llm.rag,
        "retrieve_similar_patterns",
        lambda text, language, top_k=5, pool=None: [
            RetrievedPattern(pattern_text=text, category="kyc_scam", similarity=0.99)
        ],
    )
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("leaky-1")])
    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")

    english = next(lang for lang in result["languages"] if lang["language"] == "en")
    assert english["leaked_cases"] == 1
    assert english["scored_cases"] == 0
    assert english["precision"] is None, "nothing was legitimately scored"
    assert english["leaked_case_ids"] == ["leaky-1"]
    assert result["leakage"]["held_out"] is False


def test_max_calls_refuses_rather_than_truncates(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(
        benchmark_llm, "load_corpus", lambda path=None: [case(f"c{i}") for i in range(5)]
    )
    with pytest.raises(RuntimeError, match="limit is 2"):
        benchmark_llm.run(confirm_cost=True, max_calls=2, cache_path=tmp_path / "c.json")
    assert stubbed["classify"] == 0, "refusing must happen before any spend"


def test_every_language_appears(monkeypatch, tmp_path, stubbed):
    """Same contract as the offline half: a language with no cases is a visible
    zero, not an absent row."""
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a")])
    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")
    assert len(result["languages"]) == len(benchmark_llm.LANGUAGES)


# --- Guard rejections (#113) score as the production fallback, not a crash ---


def _rejecting_classify(text, language, context, pool=None):
    raise benchmark_llm.safe_actions.UnsafeOutput("explanation asks for a credential")


def test_rejected_output_scores_as_fallback_instead_of_crashing(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(benchmark_llm.llm, "classify_message", _rejecting_classify)
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("ta-otp-001", "ta")])

    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")

    assert result["run"]["rejected_unsafe"] == ["ta-otp-001"]
    assert "offline-fallback" in result["run"]["models"]
    ta = next(lang for lang in result["languages"] if lang["language"] == "ta")
    # The fallback verdict is "suspicious", which counts as caught.
    assert ta["false_negatives"] == 0


def test_rejected_output_is_not_cached(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(benchmark_llm.llm, "classify_message", _rejecting_classify)
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a")])
    cache_path = tmp_path / "c.json"

    benchmark_llm.run(confirm_cost=True, cache_path=cache_path)

    assert benchmark_llm.load_cache(cache_path) == {}


def test_one_rejection_does_not_discard_the_other_cases(monkeypatch, tmp_path, stubbed):
    def classify(text, language, context, pool=None):
        if text == "inject":
            return _rejecting_classify(text, language, context, pool)
        return FakeClassification("high_risk", 90)

    monkeypatch.setattr(benchmark_llm.llm, "classify_message", classify)
    monkeypatch.setattr(
        benchmark_llm,
        "load_corpus",
        lambda path=None: [case("bad", text="inject"), case("good-1"), case("good-2", label="benign", text="hi")],
    )

    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")

    assert result["run"]["rejected_unsafe"] == ["bad"]
    assert result["run"]["api_calls"] == 3
    assert len(benchmark_llm.load_cache(tmp_path / "c.json")) == 2


def test_no_rejections_reports_an_empty_list(monkeypatch, tmp_path, stubbed):
    monkeypatch.setattr(benchmark_llm, "load_corpus", lambda path=None: [case("a")])
    result = benchmark_llm.run(confirm_cost=True, cache_path=tmp_path / "c.json")
    assert result["run"]["rejected_unsafe"] == []


def test_rejected_record_matches_what_the_user_is_shown():
    from app.routes.scan import _degraded_verdict

    shown = _degraded_verdict([])
    assert benchmark_llm.REJECTED_RECORD["verdict"] == shown["verdict"]
    assert benchmark_llm.REJECTED_RECORD["risk_score"] == shown["risk_score"]
