"""Fetches and caches Supabase's JWKS (JSON Web Key Set).

Newer Supabase projects sign access tokens asymmetrically (ES256) and
publish the verification public keys at a well-known JWKS endpoint, rather
than using a single shared HS256 secret. Cached in-process with a short TTL
so we're not fetching this on every request, but still pick up key
rotation without a redeploy.
"""

import time

import httpx

from app.core.config import get_settings

_CACHE_TTL_SECONDS = 3600
_cache: dict = {"keys": None, "fetched_at": 0.0}


def get_jwks() -> dict:
    now = time.time()
    if _cache["keys"] is None or now - _cache["fetched_at"] > _CACHE_TTL_SECONDS:
        settings = get_settings()
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        _cache["keys"] = response.json()["keys"]
        _cache["fetched_at"] = now
    return {"keys": _cache["keys"]}


def get_key_for_kid(kid: str) -> dict | None:
    for key in get_jwks()["keys"]:
        if key.get("kid") == kid:
            return key
    return None
