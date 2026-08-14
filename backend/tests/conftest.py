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
