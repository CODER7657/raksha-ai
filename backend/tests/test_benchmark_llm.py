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

    monkeypatch.setattr(benchmark_llm.llm, "PROMPT_VERSION", "scan-v2")
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
