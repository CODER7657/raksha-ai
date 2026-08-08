"""Text-to-speech route. Provider selection lives in app/services/tts.py.

Contract with the frontend: a 200 returns raw MP3 bytes. Any failure returns
503 with a `reason` code — the frontend treats *every* 503 here as "use the
browser voice instead", never as a user-facing error. Voice is a nice-to-have
layered on top of text that's already on screen, so it must degrade quietly.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.rate_limit import limiter
from app.services import tts

router = APIRouter(prefix="/api", tags=["tts"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts.MAX_TTS_CHARS)
    language: LanguageCode = "en"


class TTSStatusResponse(BaseModel):
    """Lets the frontend skip the network round-trip entirely when no provider
    is configured, instead of failing over on every single read-aloud."""

    available: bool
    provider: str


@router.get("/tts/status", response_model=TTSStatusResponse)
def tts_status(user_id: str = Depends(get_current_user)) -> TTSStatusResponse:
    provider = tts.active_provider()
    return TTSStatusResponse(available=provider != "none", provider=provider)


@router.post(
    "/tts",
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"},
        503: {"description": "TTS unavailable — client should use browser speech synthesis"},
    },
)
@limiter.limit(get_settings().tts_rate_limit)
def synthesize_speech(
    request: Request,
    payload: TTSRequest,
    user_id: str = Depends(get_current_user),
):
    try:
        audio, mime, from_cache = tts.synthesize(payload.text, payload.language)
    except tts.TTSUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Premium voice unavailable — falling back to device voice",
                "reason": exc.reason,
                "fallback": "browser",
            },
        )

    return Response(
        content=audio,
        media_type=mime,
        headers={
            "X-TTS-Cache": "hit" if from_cache else "miss",
            # Same text always yields the same audio, so let the browser reuse
            # it too — another layer of protection for a very small quota.
            "Cache-Control": "private, max-age=86400",
        },
    )
