from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_role_key: str  # backend-only, never sent to frontend
    # Only needed for legacy Supabase projects on shared-secret (HS256) JWT
    # signing. Newer projects use JWKS (see app/core/jwks.py) and don't need this.
    supabase_jwt_secret: str = ""

    # LLM providers (Groq primary, Gemini fallback — both free tier)
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # CORS — comma-separated list of allowed frontend origins, no wildcard
    allowed_origins: str = "http://localhost:5173"

    # ElevenLabs TTS (optional — when unset, the frontend silently uses the
    # browser's built-in speechSynthesis voices instead)
    elevenlabs_api_key: str = ""
    # Default "Lily" — a stock voice confirmed usable on the free plan. Some
    # voices are Voice Library-only and 402 for free accounts, so don't swap
    # this for an arbitrary ID without testing it first.
    elevenlabs_voice_id: str = "pFZP5JQG7iQjIQuC4Bku"
    # eleven_v3 is the only model that officially covers Gujarati/Odia. Switch
    # to eleven_flash_v2_5 to halve credit cost (0.5/char) if you only need the
    # languages it supports.
    elevenlabs_model_id: str = "eleven_v3"

    # Rate limiting
    scan_rate_limit: str = "10/minute"
    chat_rate_limit: str = "15/minute"
    # Deliberately tight: the free ElevenLabs plan is ~10k credits/month total.
    tts_rate_limit: str = "20/minute"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
