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

    # --- Text-to-speech (all optional — with none set, the frontend silently
    # uses the browser's built-in speechSynthesis voices) ---
    # "auto" prefers Sarvam, then Google, then ElevenLabs, else disabled.
    tts_provider: str = "auto"

    # Sarvam AI — built for Indian languages, and the only one of the three
    # that speaks Odia. No card needed to sign up.
    sarvam_api_key: str = ""
    sarvam_model: str = "bulbul:v2"
    # Blank = let Sarvam pick its default voice for the model.
    sarvam_speaker: str = ""

    # Google Cloud TTS. Preferred for this app: it has real native-speaker
    # neural voices for Gujarati/Hindi/Marathi/etc., where ElevenLabs' free
    # plan only exposes English voices that read Indic scripts with English
    # pronunciation.
    google_tts_api_key: str = ""
    # Optional explicit voice name (e.g. "gu-IN-Wavenet-A"). Left blank, the
    # best affordable voice for the language is discovered at runtime.
    google_tts_voice: str = ""

    # ElevenLabs — better English voices, but no usable Indic voices on the
    # free plan (the Voice Library is paid-only).
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
    tts_rate_limit: str = "20/minute"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
