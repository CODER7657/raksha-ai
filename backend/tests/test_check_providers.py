"""The error triage in the provider smoke check.

The live calls cannot be tested here — that is the whole point of the script.
What can and must be tested is the classification, because the script's value is
entirely in one distinction: a dead model needs a human, a rate limit does not.

Get that backwards and the check is either useless (misses a retirement) or
gets muted (alerts every time Groq throttles), and a muted check is worse than
no check — the same failure as `pytest || true` in #22.
"""

import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_providers",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_providers.py",
)
check_providers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_providers)


@pytest.mark.parametrize(
    "message, expected",
    [
        # The exact string that started all this.
        (
            (
                "404 models/gemini-1.5-flash is not found for API version "
                "v1beta, or is not supported for generateContent."
            ),
            "dead",
        ),
        ("This model models/gemini-2.0-flash is no longer available.", "dead"),
        ("NotFound: model not found", "dead"),
        ("429 Too Many Requests", "rate_limited"),
        ("Rate limit reached for model llama-3.3-70b-versatile", "rate_limited"),
        ("RESOURCE_EXHAUSTED: quota exceeded", "rate_limited"),
        ("401 Unauthorized", "unauthorized"),
        ("API key not valid. Please pass a valid API key.", "unauthorized"),
        ("503 Service Unavailable", "degraded"),
        ("Read timed out", "degraded"),
    ],
)
def test_error_is_triaged_by_what_it_needs_from_a_human(message, expected):
    status, _ = check_providers.classify_error(Exception(message))
    assert status == expected


def test_only_dead_and_unauthorized_demand_action():
    """A rate limit must not fail the run. This is the assertion that keeps the
    weekly check trustworthy enough to stay switched on."""
    assert check_providers.Result("x", "dead").needs_a_human
    assert check_providers.Result("x", "unauthorized").needs_a_human
    assert not check_providers.Result("x", "rate_limited").needs_a_human
    assert not check_providers.Result("x", "degraded").needs_a_human
    assert not check_providers.Result("x", "ok").needs_a_human


def test_detail_is_one_line_and_bounded():
    """Provider errors carry multi-line dumps; the report stays readable."""
    _, detail = check_providers.classify_error(Exception("404 gone\n" + "x" * 500))
    assert "\n" not in detail
    assert len(detail) <= 160


def test_every_status_has_a_display_symbol():
    for status in ("ok", "rate_limited", "skipped", "degraded", "dead", "unauthorized"):
        assert status in check_providers._SYMBOL
