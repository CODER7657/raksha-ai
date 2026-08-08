"""ElevenLabs text-to-speech, proxied through the backend.

Why proxy instead of calling ElevenLabs from the browser: the API key would be
readable in the frontend bundle by anyone who opens devtools, and the quota is
tiny (see below), so a leaked key is a real problem.

Quota reality check — the free ElevenLabs plan is ~10,000 credits/month at
1 credit/character (0.5 for the flash model). A ~300-character chat reply is
~300 credits, so the whole month is roughly 30-60 spoken replies ACROSS ALL
USERS. That drives three decisions here:

  1. Responses are cached by (text, language, voice, model) — re-reading the
     same reply, or two users asking the same common question, costs nothing
     the second time.
  2. `MAX_TTS_CHARS` caps a single request so one long reply can't burn a
     large slice of the month.
  3. Every failure path (no key, quota exhausted, ElevenLabs down) raises
     `TTSUnavailable` rather than a generic 500, so the route can tell the
     frontend "fall back to the browser voice" instead of just breaking.

No new dependencies: httpx is already pinned in requirements.txt. This matters —
the Render free tier is 512MB RAM and has OOM-crashed twice before (see the
comments in app/services/transcribe.py), so this feature deliberately adds zero
install weight and a strictly bounded cache.
"""

import hashlib
from collections import OrderedDict

from app.core import languages
from app.core.config import get_settings

#: Roughly one long chat reply. Keeps a single call from eating the month.
MAX_TTS_CHARS = 800

#: ~50KB per clip, so this is a few MB at worst — safe for a 512MB dyno.
_CACHE_MAX_ENTRIES = 64

_audio_cache: OrderedDict[str, bytes] = OrderedDict()

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class TTSUnavailable(Exception):
    """Raised when ElevenLabs can't serve this request for any reason.

    The caller should degrade to browser speechSynthesis, not surface an error.
    `reason` is a short machine-readable code for logging/telemetry.
    """

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def is_configured() -> bool:
    return bool(get_settings().elevenlabs_api_key)


def _cache_key(text: str, voice_id: str, model_id: str, language: str) -> str:
    raw = f"{language}\x00{voice_id}\x00{model_id}\x00{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> bytes | None:
    audio = _audio_cache.get(key)
    if audio is not None:
        _audio_cache.move_to_end(key)  # LRU: refresh recency on hit
    return audio


def _cache_put(key: str, audio: bytes) -> None:
    _audio_cache[key] = audio
    _audio_cache.move_to_end(key)
    while len(_audio_cache) > _CACHE_MAX_ENTRIES:
        _audio_cache.popitem(last=False)


def synthesize(text: str, language: str) -> tuple[bytes, bool]:
    """Return (mp3_bytes, from_cache).

    Raises TTSUnavailable on every failure path so the caller can fall back to
    the browser voice rather than showing the user an error.
    """
    settings = get_settings()

    if not settings.elevenlabs_api_key:
        raise TTSUnavailable("not_configured", "ELEVENLABS_API_KEY is not set")

    text = text.strip()
    if not text:
        raise TTSUnavailable("empty_text")
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    voice_id = settings.elevenlabs_voice_id
    model_id = settings.elevenlabs_model_id

    key = _cache_key(text, voice_id, model_id, language)
    cached = _cache_get(key)
    if cached is not None:
        return cached, True

    import httpx

    lang = languages.get_language(language)

    payload: dict = {
        "text": text,
        "model_id": model_id,
        # Always send the language explicitly. This is a correctness guard, not
        # a hint: without it a model that doesn't know the script (e.g.
        # multilingual_v2 given Gujarati) happily returns 200 and mispronounced
        # gibberish. With it, ElevenLabs 400s with "unsupported_language" and we
        # fall back to the browser voice instead of playing garbage at someone
        # who can't read the text on screen.
        "language_code": lang.code,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            # Indic scripts benefit from a slightly slower, clearer read —
            # these users are often hearing safety instructions under stress.
            "speed": 0.95,
        },
    }

    try:
        response = httpx.post(
            ELEVENLABS_TTS_URL.format(voice_id=voice_id),
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
    except Exception as exc:
        raise TTSUnavailable("network_error", str(exc)) from exc

    if response.status_code == 400 and "unsupported_language" in response.text:
        # Verified against the live API: eleven_v3 covers 11 of the 12 app
        # languages — Odia ("or") is the sole gap. eleven_multilingual_v2 and
        # eleven_flash_v2_5 additionally reject Gujarati. Browser voice it is.
        raise TTSUnavailable("unsupported_language", f"{model_id} cannot speak {lang.english_name}")
    if response.status_code == 401:
        raise TTSUnavailable("bad_key", "ElevenLabs rejected the API key")
    if response.status_code == 402:
        raise TTSUnavailable("quota_or_plan", response.text[:200])
    if response.status_code == 429:
        raise TTSUnavailable("rate_limited", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    audio = response.content
    if not audio:
        raise TTSUnavailable("empty_audio")

    _cache_put(key, audio)
    return audio, False
