"""Retrieval failure must degrade the live routes, not 500 them.

Found by contract fuzzing (tests/test_contract_fuzz.py): with the embedding
provider down, `/api/scan/text`, `/api/scan/email` and `/api/chat` raised
straight through `rag.retrieve_similar_patterns`.
"""

import logging

import pytest

from app.services import rag
from app.services.rag import RetrievedPattern


def _boom(*args, **kwargs):
    raise ConnectionError("embedding provider unreachable")


def test_returns_patterns_when_retrieval_works(monkeypatch):
    expected = [RetrievedPattern(pattern_text="share otp", category="otp", similarity=0.8)]
    monkeypatch.setattr(rag, "retrieve_similar_patterns", lambda text, language: expected)
    assert rag.retrieve_or_empty("x", "en") == expected


@pytest.mark.parametrize(
    "failure",
    [ConnectionError("down"), TimeoutError("slow"), RuntimeError("rpc failed"), KeyError("similarity")],
)
def test_any_retrieval_failure_becomes_no_grounding(monkeypatch, failure):
    def fail(*a, **k):
        raise failure

    monkeypatch.setattr(rag, "retrieve_similar_patterns", fail)
    assert rag.retrieve_or_empty("x", "en") == []


def test_failure_is_logged_without_the_message_text(monkeypatch, caplog):
    monkeypatch.setattr(rag, "retrieve_similar_patterns", _boom)
    with caplog.at_level(logging.WARNING, logger="app.services.rag"):
        rag.retrieve_or_empty("my OTP is 482913", "en")
    assert "Pattern retrieval failed" in caplog.text
    # §2.4: no message text in logs.
    assert "482913" not in caplog.text


def test_batch_callers_still_see_the_failure(monkeypatch):
    """The benchmark and red team must not silently measure an ungrounded system."""
    monkeypatch.setattr(rag, "embed", _boom)
    with pytest.raises(ConnectionError):
        rag.retrieve_similar_patterns("x", "en")


def test_live_routes_use_the_degrading_version():
    import inspect

    from app.routes import chat, scan

    for module in (scan, chat):
        source = inspect.getsource(module)
        assert "rag.retrieve_or_empty(" in source
        assert "rag.retrieve_similar_patterns(" not in source


def test_a_provider_error_that_echoes_the_request_is_not_logged(monkeypatch, caplog):
    """Real SDK errors can quote the request body; only the type may be logged."""

    def echoing(text, language):
        raise ValueError(f"400 Bad Request: content={text!r}")

    monkeypatch.setattr(rag, "retrieve_similar_patterns", echoing)
    with caplog.at_level(logging.WARNING, logger="app.services.rag"):
        rag.retrieve_or_empty("my OTP is 482913", "en")
    assert "ValueError" in caplog.text
    assert "482913" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
