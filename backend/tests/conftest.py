"""Test-run settings, applied before any `app.*` module is imported.

`app.routes.scan` calls `get_settings()` at import time (the rate-limit
decorator is evaluated when the module is read), so `Settings()` is constructed
during collection. Without `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the
environment that raises a pydantic ValidationError and the whole suite fails to
collect — which is what happens on a clean CI runner, where there is no `.env`.

Stub values rather than real ones: every test in this suite injects its own
fake Supabase client, so a test must never hold credentials that could reach a
live project. `setdefault` so an explicitly exported variable still wins, and
these are applied here rather than in `pytest.ini`'s `env` so that no extra
plugin is needed to run the tests.
"""

import os

os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "stub-service-role-key")

# Imported after the defaults above, not before: `app.core.config` constructs
# nothing at import time, but keeping the order explicit means a future import
# that does construct something still finds the stub values already set.
import pytest

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def settings_ignore_dotenv(monkeypatch):
    """No test may see the developer's real credentials (#77).

    `Settings` declares `env_file=".env"`, and pydantic-settings treats the
    dotenv file as a source in its own right — separate from the process
    environment. `monkeypatch.delenv` removes the variable and nothing else, so
    a field the test believes it has cleared silently falls through to whatever
    is in `backend/.env`.

    That is not hypothetical. It made three `test_key_pools.py` assertions fail
    on any machine with keys configured while passing in CI, where no `.env`
    exists — a test lying in exactly the environment where someone has just
    finished setting up, and printing a real key prefix into the diff while
    doing it.

    Neutralising the source here rather than in the one file that noticed:
    nothing else stops the next settings-dependent test from acquiring the same
    dependency, and it would fail the same confusing way.

    `setitem` rather than assignment so pytest restores the original after each
    test, leaving the class as the application sees it.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
