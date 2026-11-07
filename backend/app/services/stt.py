"""Speech-to-text with a provider ladder: Sarvam first, Groq Whisper second.

Sarvam's saaras models are trained on Indic languages and return the right
script for Gujarati, which small Whisper models do not:

    expected     તમારો OTP અથવા UPI PIN કોઈને ન આપો.
    whisper base तमारो खवाभाल वपे पे कोणे ने आपो

The fallback used to be a local faster-whisper `base` model, the largest that
fitted Render's 512MB free tier, and it produced the line above. It is now
Groq's hosted `whisper-large-v3`: no model in the process, so the backend fits a
serverless function, and the large model is the one that knows Gujarati script.

Both rungs are network calls, so both can fail. A failure on one quietly moves
to the next, the same degrade-quietly rule the TTS layer follows. If every rung
fails, `transcribe` raises STTUnavailable so the route can say "voice is down"
instead of the misleading "no speech found".
"""

import httpx

from app.core.config import get_settings

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

#: App language code -> Sarvam BCP-47 code. Mirrors the TTS mapping, including
#: Odia's non-standard "od-IN". Anything missing is sent as "unknown", which
#: asks Sarvam to auto-detect rather than failing outright — better than
#: refusing to transcribe at all for, say, Urdu.
_SARVAM_STT_LANGUAGES = {
    "en": "en-IN",
    "hi": "hi-IN",
    "gu": "gu-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "pa": "pa-IN",
    "or": "od-IN",
}

#: Product languages Whisper knows by the same ISO 639-1 code. Odia is not one
#: of Whisper's languages, so it is left to auto-detect instead of sending a
#: code the API would reject.
_WHISPER_LANGUAGES = {"en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "ur"}

#: Per provider. Two rungs means a voice scan can wait twice this before the
#: route answers 503, so it is kept short enough for a person to still be there.
_TIMEOUT_S = 20.0


class STTUnavailable(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def active_provider() -> str:
    """The first rung tried: "sarvam" or "groq". "auto" picks Sarvam when its
    key is set. "whisper" is accepted for old configs and means Groq now."""
    settings = get_settings()
    configured = settings.stt_provider.lower()

    if configured == "auto":
        return "sarvam" if settings.sarvam_api_key else "groq"
    if configured == "whisper":
        return "groq"
    return configured


def _raise_for_status(response: httpx.Response, api_key: str) -> None:
    if response.status_code == 200:
        return
    detail = response.text[:200]
    if api_key:
        detail = detail.replace(api_key, "***")
    if response.status_code in (401, 403):
        raise STTUnavailable("bad_key", detail)
    if response.status_code == 402:
        raise STTUnavailable("quota_or_plan", detail)
    if response.status_code == 413:
        raise STTUnavailable("too_large", detail)
    if response.status_code == 429:
        raise STTUnavailable("rate_limited", detail)
    raise STTUnavailable(f"http_{response.status_code}", detail)


def _transcribe_sarvam(file_bytes: bytes, language: str, filename: str, content_type: str) -> str:
    settings = get_settings()
    api_key = settings.sarvam_api_key
    if not api_key:
        raise STTUnavailable("not_configured", "SARVAM_API_KEY is not set")

    data = {
        "model": settings.sarvam_stt_model,
        "language_code": _SARVAM_STT_LANGUAGES.get(language, "unknown"),
    }

    try:
        response = httpx.post(
            SARVAM_STT_URL,
            headers={"api-subscription-key": api_key},
            files={"file": (filename or "audio.webm", file_bytes, content_type or "audio/webm")},
            data=data,
            timeout=_TIMEOUT_S,
        )
    except Exception as exc:
        raise STTUnavailable("network_error", type(exc).__name__) from exc

    _raise_for_status(response, api_key)
    return (response.json().get("transcript") or "").strip()


def _transcribe_groq(file_bytes: bytes, language: str, filename: str, content_type: str) -> str:
    from app.services import llm

    api_key = llm.keys_for(llm.INTERACTIVE)[0]
    if not api_key:
        raise STTUnavailable("not_configured", "GROQ_API_KEY is not set")

    data = {"model": llm.GROQ_STT_MODEL, "response_format": "json", "temperature": "0"}
    if language in _WHISPER_LANGUAGES:
        data["language"] = language

    try:
        response = httpx.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename or "audio.webm", file_bytes, content_type or "audio/webm")},
            data=data,
            timeout=_TIMEOUT_S,
        )
    except Exception as exc:
        raise STTUnavailable("network_error", type(exc).__name__) from exc

    _raise_for_status(response, api_key)
    return (response.json().get("text") or "").strip()


def transcribe(
    file_bytes: bytes,
    language: str,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
) -> str:
    """Transcribe audio, preferring Sarvam and falling back to Groq Whisper.

    Returns "" when a provider answered but heard no speech. Raises
    STTUnavailable only when no provider could answer at all.
    """
    ladder = [_transcribe_groq]
    if active_provider() == "sarvam":
        ladder.insert(0, _transcribe_sarvam)

    last_error: STTUnavailable | None = None
    heard_nothing = False
    for rung in ladder:
        try:
            transcript = rung(file_bytes, language, filename, content_type)
        except STTUnavailable as exc:
            last_error = exc
            continue
        if transcript:
            return transcript
        # An empty result is not an error, but the next rung may still find speech.
        heard_nothing = True

    if heard_nothing or last_error is None:
        return ""
    raise last_error
