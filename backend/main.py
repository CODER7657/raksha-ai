from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.rate_limit import limiter
from app.routes import chat, practice, scan, tts, upi

settings = get_settings()

app = FastAPI(title="Raksha AI API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# No wildcard origin — only the exact frontend URL(s) from ALLOWED_ORIGINS env var.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(scan.router)
app.include_router(upi.router)
app.include_router(chat.router)
app.include_router(practice.router)
app.include_router(tts.router)


@app.get("/health")
def health() -> dict:
    """Render/uptime-monitor ping target — also what wakes the free-tier
    instance out of its cold-start sleep before a demo."""
    return {"status": "ok"}
