"""Contract fuzzing: no route may answer 500 (roadmap §2.3 item 3).

Schemathesis reads the app's own OpenAPI schema and generates requests for every
operation: valid bodies, boundary values, wrong types, missing fields. The one
check is `no_unhandled_server_error`. A 4xx is the API refusing bad input, which is its
job; a 500 is the API not having thought about that input, and on the live path
it is also what a user mid-scam would see instead of a verdict.

Run twice, because the two worlds fail differently:

* **providers up**: the LLM, embeddings and chat model answer with valid output,
  so generated input reaches the parsing and persistence code behind them.
* **providers down**: every provider raises, and the network is closed. §2.4
  asks for a clear 503/504 or the offline fallback when a provider fails, never
  a 500.

Nothing here can reach a real service. Auth is overridden to a fixed user,
Supabase is a permissive in-memory fake, and in both modes any socket connection
or DNS lookup raises, so a call site nobody stubbed fails loudly instead of
quietly spending quota.

Examples per operation default to 25 (about a second per mode locally). Set
`FUZZ_EXAMPLES` to go deeper (200 per operation was run before merging).
"""

import json
import os
import socket
from types import SimpleNamespace

import pytest
import schemathesis
from hypothesis import HealthCheck, settings

import main
from app.core import auth, supabase_client
from app.rate_limit import limiter
from app.services import chat, embeddings, llm, rag

FUZZ_EXAMPLES = int(os.environ.get("FUZZ_EXAMPLES", "25"))
FAKE_USER = "00000000-0000-4000-8000-000000000001"


class FakeQuery:
    """Accepts any Supabase call chain and returns an empty result.

    `table(...).select(...).eq(...).order(...).execute()`, `rpc(...).execute()`,
    `storage.from_(...)...`: every attribute is another FakeQuery, every call
    returns one, and `execute()` ends the chain with no rows. Empty is the honest
    default: routes must already cope with a user who has no history.
    """

    def __getattr__(self, name):
        return FakeQuery()

    def __call__(self, *args, **kwargs):
        return FakeQuery()

    def execute(self):
        return SimpleNamespace(data=[], count=0)


def _no_network(*args, **kwargs):
    raise OSError("network is disabled in the contract fuzz tests")


def _provider_down(*args, **kwargs):
    raise ConnectionError("provider unreachable (simulated)")


_VALID_CLASSIFICATION = json.dumps(
    {
        "risk_score": 90,
        "verdict": "high_risk",
        "flagged_phrases": [],
        "explanation": "Urgency and a request to act on an unknown link.",
        "recommended_action_id": "do_not_share_credentials",
    }
)


def _isolate(mp: pytest.MonkeyPatch) -> None:
    """Stubs shared by both modes."""
    main.app.dependency_overrides[auth.get_current_user] = lambda: FAKE_USER
    mp.setattr(limiter, "enabled", False)

    fake = FakeQuery()
    mp.setattr(supabase_client, "get_supabase", lambda: fake)
    # Modules that did `from app.core.supabase_client import get_supabase`
    # hold their own reference, so each one is patched where it is used.
    import app.routes.insights
    import app.routes.scan
    import app.services.agent_control
    import app.services.domain_age
    import app.services.pattern_review
    import app.services.rag
    import app.services.verdict_cache
    import app.services.verdict_revision

    for module in (
        app.routes.insights,
        app.routes.scan,
        app.services.agent_control,
        app.services.domain_age,
        app.services.pattern_review,
        app.services.rag,
        app.services.verdict_cache,
        app.services.verdict_revision,
    ):
        if hasattr(module, "get_supabase"):
            mp.setattr(module, "get_supabase", lambda: fake)

    mp.setattr(socket.socket, "connect", _no_network)
    mp.setattr(socket, "getaddrinfo", _no_network)
    mp.setattr(socket, "create_connection", _no_network)


@pytest.fixture(scope="module")
def providers_up():
    with pytest.MonkeyPatch.context() as mp:
        _isolate(mp)
        mp.setattr(
            llm,
            "complete",
            lambda system, user, pool=llm.INTERACTIVE: llm.Completion(
                text=_VALID_CLASSIFICATION, provider="groq", model=llm.GROQ_MODEL
            ),
        )
        zero_vector = lambda *a, **k: [0.0] * embeddings.EMBEDDING_DIM
        mp.setattr(embeddings, "embed", zero_vector)
        mp.setattr(rag, "embed", zero_vector)  # rag imports it by name
        mp.setattr(chat, "chat_reply", lambda *a, **k: "Do not share any code.")
        yield
    main.app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def providers_down():
    with pytest.MonkeyPatch.context() as mp:
        _isolate(mp)
        mp.setattr(llm, "_call_groq", _provider_down)
        mp.setattr(llm, "_call_gemini", _provider_down)
        mp.setattr(embeddings, "embed", _provider_down)
        mp.setattr(rag, "embed", _provider_down)
        mp.setattr(chat, "_call_groq", _provider_down)
        mp.setattr(chat, "_call_gemini", _provider_down)
        yield
    main.app.dependency_overrides.clear()


@schemathesis.check
def no_unhandled_server_error(ctx, response, case):
    """5xx is a failure except 503/504, the deliberate "provider unavailable"
    answers §2.4 asks for (the TTS route's browser-voice fallback is a 503 by
    contract). The built-in `not_a_server_error` rejects those too. Unhandled
    exceptions propagate through the ASGI transport and fail the test anyway."""
    if response.status_code >= 500 and response.status_code not in (503, 504):
        raise AssertionError(
            f"{response.status_code} from {case.method} {case.formatted_path}: {response.text[:200]}"
        )


schema = schemathesis.openapi.from_asgi("/openapi.json", main.app)

_FUZZ_SETTINGS = settings(
    max_examples=FUZZ_EXAMPLES,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


@schema.parametrize()
@_FUZZ_SETTINGS
def test_no_route_returns_500_when_providers_answer(providers_up, case):
    case.call_and_validate(checks=[no_unhandled_server_error])


@schema.parametrize()
@_FUZZ_SETTINGS
def test_no_route_returns_500_when_providers_fail(providers_down, case):
    case.call_and_validate(checks=[no_unhandled_server_error])


def test_the_schema_covers_every_route():
    """Fuzzing an empty or partial schema would pass vacuously."""
    documented = {
        (path, method.upper())
        for path, item in main.app.openapi()["paths"].items()
        for method in item
    }
    assert len(documented) >= 20
    assert ("/health", "GET") in documented
