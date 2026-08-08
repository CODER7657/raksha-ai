"""Speech-to-text with a provider ladder: Sarvam first, faster-whisper second.

Why: faster-whisper's `base` model — the largest that fits Render's 512MB free
tier — cannot handle Gujarati. Feeding it a clean Gujarati clip returns
Devanagari (Hindi script) with the words garbled:

    expected     તમારો OTP અથવા UPI PIN કોઈને ન આપો.
    whisper base तमारो खवाभाल वपे पे कोणे ने आपो

The language hint is passed correctly; the model is simply too small. Going up
to `small` is what OOM-crashed the instance twice before (see transcribe.py).

Sarvam's saaras models are trained on Indic languages and return the correct
script. Whisper stays as the fallback so voice input keeps working when the
Sarvam key is absent, its credits run out, or the network fails — the same
degrade-quietly rule the TTS layer follows.
"""

from app.core.config import get_settings
from app.services.transcribe import transcribe_audio as _whisper_transcribe

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

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


class STTUnavailable(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def active_provider() -> str:
    settings = get_settings()
    configured = settings.stt_provider.lower()

    if configured == "auto":
        return "sarvam" if settings.sarvam_api_key else "whisper"

    return configured


def _transcribe_sarvam(file_bytes: bytes, language: str, filename: str, content_type: str) -> str:
    settings = get_settings()
    api_key = settings.sarvam_api_key
    if not api_key:
        raise STTUnavailable("not_configured", "SARVAM_API_KEY is not set")

    import httpx

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
            timeout=60.0,
        )
    except Exception as exc:
        raise STTUnavailable("network_error", str(exc)) from exc

    if response.status_code in (401, 403):
        raise STTUnavailable("bad_key", response.text[:200])
    if response.status_code == 402:
        raise STTUnavailable("quota_or_plan", response.text[:200])
    if response.status_code == 429:
        raise STTUnavailable("rate_limited", response.text[:200])
    if response.status_code != 200:
        raise STTUnavailable(f"http_{response.status_code}", response.text[:200])

    return (response.json().get("transcript") or "").strip()


def transcribe(
    file_bytes: bytes,
    language: str,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
) -> str:
    """Transcribe audio, preferring Sarvam and falling back to local Whisper.

    Never raises for provider problems — a Sarvam failure quietly becomes a
    Whisper attempt, because a worse transcript beats no transcript.
    """
    if active_provider() == "sarvam":
        try:
            transcript = _transcribe_sarvam(file_bytes, language, filename, content_type)
            if transcript:
                return transcript
            # An empty result is not an error, but Whisper may still find speech.
        except STTUnavailable:
            pass

    return _whisper_transcribe(file_bytes, language)
