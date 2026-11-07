"""Which address the rate limiter counts against (app/rate_limit.py)."""

import pytest
from starlette.requests import Request

from app.rate_limit import client_key


def request(headers: dict[str, str], peer: str = "10.0.0.9") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 1234),
    }
    return Request(scope)


def test_on_vercel_the_edge_address_is_used(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert client_key(request({"x-real-ip": "203.0.113.7"})) == "203.0.113.7"


def test_on_vercel_without_the_header_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert client_key(request({})) == "10.0.0.9"
    assert client_key(request({"x-real-ip": "  "})) == "10.0.0.9"


@pytest.mark.parametrize("vercel", [None, "0", ""])
def test_elsewhere_a_client_cannot_choose_its_bucket(monkeypatch, vercel):
    if vercel is None:
        monkeypatch.delenv("VERCEL", raising=False)
    else:
        monkeypatch.setenv("VERCEL", vercel)
    assert client_key(request({"x-real-ip": "1.2.3.4"})) == "10.0.0.9"
