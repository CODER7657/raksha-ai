"""The provider ladder, and why its failures have to be audible.

`gemini-1.5-flash` was retired and every fallback attempt 404'd. Nothing
surfaced it: the Groq exception was discarded, and the only symptom was the
combined "Both Groq and Gemini failed", which reads like a provider outage
rather than a model id that needed changing. These tests pin the behaviour that
makes the next retirement visible on the first occurrence.
"""

import logging

import pytest

from app.services import llm


def test_groq_failure_is_logged_not_swallowed(monkeypatch, caplog):
    """The silent `except Exception: raw = None` is what hid the dead fallback."""
    monkeypatch.setattr(llm, "_call_groq", _raise(RuntimeError("groq down")))
    monkeypatch.setattr(llm, "_call_gemini", lambda *a: _VALID_JSON)

    with caplog.at_level(logging.WARNING, logger="app.services.llm"):
        result = llm.classify_message("Share your OTP", "en", "")

    assert result.provider == "gemini"
    assert any("Groq" in r.message for r in caplog.records), (
        "a failed primary provider must leave a trace, or a dead rung stays invisible"
    )


def test_gemini_failure_is_logged_before_raising(monkeypatch, caplog):
    monkeypatch.setattr(llm, "_call_groq", _raise(RuntimeError("groq down")))
    monkeypatch.setattr(llm, "_call_gemini", _raise(RuntimeError("404 model not found")))

    with (
        caplog.at_level(logging.WARNING, logger="app.services.llm"),
        pytest.raises(RuntimeError, match="Both Groq and Gemini failed"),
    ):
        llm.classify_message("Share your OTP", "en", "")

    assert any(r.levelno >= logging.ERROR for r in caplog.records)
    # The underlying cause must survive, or "both failed" is all anyone ever sees.
    assert any("404" in (r.exc_text or "") for r in caplog.records)


def test_the_ladder_reports_which_rung_answered(monkeypatch):
    """The stamp travels into the audit record, so it has to be observed rather
    than assumed — a run that silently fell back must say so."""
    monkeypatch.setattr(llm, "_call_groq", lambda *a: _VALID_JSON)
    assert llm.classify_message("x", "en", "").provider == "groq"

    monkeypatch.setattr(llm, "_call_groq", _raise(RuntimeError("rate limited")))
    monkeypatch.setattr(llm, "_call_gemini", lambda *a: _VALID_JSON)

    fell_back = llm.classify_message("x", "en", "")
    assert fell_back.provider == "gemini"
    assert fell_back.model == llm.GEMINI_MODEL


@pytest.mark.parametrize("model", [llm.GROQ_MODEL, llm.GEMINI_MODEL])
def test_models_are_pinned_not_floating_aliases(model: str):
    """`gemini-flash-latest` and friends resolve to whatever is newest today.
    An auto-advancing model moves verdicts underneath a stamped PROMPT_VERSION,
    which defeats the reproducibility the stamp exists for (ARCHITECTURE §03).
    """
    assert not model.endswith("-latest"), f"{model} floats; pin an exact version"


_VALID_JSON = (
    '{"risk_score": 90, "verdict": "high_risk", "flagged_phrases": ["OTP"], '
    '"explanation": "e", "recommended_action": "a"}'
)


def _raise(exc: Exception):
    def _fn(*_args, **_kwargs):
        raise exc

    return _fn
