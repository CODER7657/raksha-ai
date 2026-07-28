from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Server-side Supabase client using the service role key.

    Only ever call this from backend code, never expose this key to the
    frontend. Because we authenticate the user ourselves in `core/auth.py`
    and scope every query by that verified user_id, the service key is used
    narrowly — RLS is still enabled and still the source of truth if this
    client is ever queried without an explicit user_id filter.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
