from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_role_key: str  # backend-only, never sent to frontend
    supabase_jwt_secret: str

    # LLM providers (Groq primary, Gemini fallback — both free tier)
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # CORS — comma-separated list of allowed frontend origins, no wildcard
    allowed_origins: str = "http://localhost:5173"

    # Rate limiting
    scan_rate_limit: str = "10/minute"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
