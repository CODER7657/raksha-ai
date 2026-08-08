"""Text-to-speech, proxied through the backend so no API key reaches the browser.

Two providers, selected by config:

  google (default)
      Has genuine native-speaker neural voices for Indic languages —
      gu-IN, hi-IN, mr-IN, bn-IN, ta-IN, kn-IN, ml-IN, pa-IN, ur-IN.
      Free tier is ~1M characters/month, which this app will not realistically
      exhaust.

  elevenlabs
      Excellent English voices, but on the free plan the Voice Library is
      blocked, leaving only English-native stock voices. Those *accept*
      Gujarati text and return confident, fluent-sounding audio that is
      actually an English speaker reading Gujarati letters — unusable, and
      worse than an honest failure because it sounds fine to someone who
      doesn't speak the language. Kept as an option for English-only setups.

Whatever the provider, every failure raises `TTSUnavailable` so the route can
tell the frontend to fall back to the browser's own voice. Voice is an
enhancement layered over text that's already on screen; it must never become a
hard dependency.

No new dependencies — httpx is already pinned in requirements.txt. That matters
because the Render free tier is 512MB RAM and has OOM-crashed twice before (see
app/services/transcribe.py), so the cache here is strictly bounded.
"""

import base64
import hashlib
from collections import OrderedDict

from app.core import languages
from app.core.config import get_settings

#: Roughly one long chat reply.
MAX_TTS_CHARS = 800

#: ~50KB per clip, so a few MB at worst.
_CACHE_MAX_ENTRIES = 64

_audio_cache: OrderedDict[str, bytes] = OrderedDict()

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_VOICES_URL = "https://texttospeech.googleapis.com/v1/voices"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class TTSUnavailable(Exception):
    """Raised when TTS can't serve this request for any reason.

    The caller should degrade to browser speechSynthesis, not surface an error.
    """

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def active_provider() -> str:
    """Resolves "auto" to whichever provider actually has credentials."""
    settings = get_settings()
    configured = settings.tts_provider.lower()

    if configured == "auto":
        if settings.google_tts_api_key:
            return "google"
        if settings.elevenlabs_api_key:
            return "elevenlabs"
        return "none"

    return configured


def is_configured() -> bool:
    return active_provider() != "none"


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

def _cache_key(text: str, language: str, provider: str, voice: str) -> str:
    raw = f"{provider}\x00{voice}\x00{language}\x00{text}"
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


# --------------------------------------------------------------------------
# Google Cloud Text-to-Speech
# --------------------------------------------------------------------------

#: Newer voice families sound markedly better; prefer them when a language has
#: several. Ordered best-first.
_GOOGLE_VOICE_TIERS = ("Chirp3-HD", "Neural2", "Studio", "Wavenet", "Standard")

#: language code -> resolved Google voice name. Populated on first use.
_google_voice_cache: dict[str, str | None] = {}


def _google_voice_rank(voice_name: str) -> int:
    for index, tier in enumerate(_GOOGLE_VOICE_TIERS):
        if tier.lower() in voice_name.lower():
            return index
    return len(_GOOGLE_VOICE_TIERS)


def _pick_google_voice(bcp47: str, api_key: str) -> str | None:
    """Ask Google which voices exist for this language and take the best one.

    Deliberately discovered at runtime rather than hardcoded: voice names change
    as Google adds and retires them, and a stale hardcoded name would fail in
    production long after anyone remembers why. A language with no voices at all
    (Odia, at time of writing) simply resolves to None and falls back.
    """
    if bcp47 in _google_voice_cache:
        return _google_voice_cache[bcp47]

    import httpx

    try:
        response = httpx.get(
            GOOGLE_VOICES_URL,
            params={"key": api_key, "languageCode": bcp47},
            timeout=15.0,
        )
    except Exception as exc:
        raise TTSUnavailable("network_error", str(exc)) from exc

    if response.status_code == 400:
        raise TTSUnavailable("bad_key", response.text[:200])
    if response.status_code in (401, 403):
        raise TTSUnavailable("bad_key", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    voices = response.json().get("voices", [])
    if not voices:
        _google_voice_cache[bcp47] = None
        return None

    best = sorted(voices, key=lambda v: _google_voice_rank(v.get("name", "")))[0]
    name = best.get("name")
    _google_voice_cache[bcp47] = name
    return name


def _synthesize_google(text: str, language: str) -> tuple[bytes, str]:
    """Returns (mp3_bytes, voice_name)."""
    settings = get_settings()
    api_key = settings.google_tts_api_key
    if not api_key:
        raise TTSUnavailable("not_configured", "GOOGLE_TTS_API_KEY is not set")

    lang = languages.get_language(language)
    voice_name = _pick_google_voice(lang.bcp47, api_key)
    if not voice_name:
        raise TTSUnavailable("unsupported_language", f"Google has no voice for {lang.english_name}")

    import httpx

    payload = {
        "input": {"text": text},
        "voice": {"languageCode": lang.bcp47, "name": voice_name},
        "audioConfig": {
            "audioEncoding": "MP3",
            # Slightly slower than default: these are safety instructions, often
            # heard by someone who is panicking.
            "speakingRate": 0.95,
        },
    }

    try:
        response = httpx.post(
            GOOGLE_TTS_URL, params={"key": api_key}, json=payload, timeout=30.0
        )
    except Exception as exc:
        raise TTSUnavailable("network_error", str(exc)) from exc

    if response.status_code in (401, 403):
        raise TTSUnavailable("bad_key", response.text[:200])
    if response.status_code == 429:
        raise TTSUnavailable("rate_limited", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    encoded = response.json().get("audioContent")
    if not encoded:
        raise TTSUnavailable("empty_audio")

    return base64.b64decode(encoded), voice_name


# --------------------------------------------------------------------------
# ElevenLabs
# --------------------------------------------------------------------------

def _synthesize_elevenlabs(text: str, language: str) -> tuple[bytes, str]:
    settings = get_settings()
    api_key = settings.elevenlabs_api_key
    if not api_key:
        raise TTSUnavailable("not_configured", "ELEVENLABS_API_KEY is not set")

    import httpx

    lang = languages.get_language(language)
    voice_id = settings.elevenlabs_voice_id
    model_id = settings.elevenlabs_model_id

    payload = {
        "text": text,
        "model_id": model_id,
        # Sending the language explicitly makes ElevenLabs reject what it can't
        # speak, instead of returning fluent-sounding nonsense.
        "language_code": lang.code,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 0.95},
    }

    try:
        response = httpx.post(
            ELEVENLABS_TTS_URL.format(voice_id=voice_id),
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
    except Exception as exc:
        raise TTSUnavailable("network_error", str(exc)) from exc

    if response.status_code == 400 and "unsupported_language" in response.text:
        raise TTSUnavailable("unsupported_language", f"{model_id} cannot speak {lang.english_name}")
    if response.status_code == 401:
        raise TTSUnavailable("bad_key", "ElevenLabs rejected the API key")
    if response.status_code == 402:
        raise TTSUnavailable("quota_or_plan", response.text[:200])
    if response.status_code == 429:
        raise TTSUnavailable("rate_limited", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    if not response.content:
        raise TTSUnavailable("empty_audio")

    return response.content, voice_id


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def synthesize(text: str, language: str) -> tuple[bytes, bool]:
    """Return (mp3_bytes, from_cache). Raises TTSUnavailable on any failure."""
    provider = active_provider()
    if provider == "none":
        raise TTSUnavailable("not_configured", "No TTS provider is configured")

    text = text.strip()
    if not text:
        raise TTSUnavailable("empty_text")
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    settings = get_settings()
    # Voice is part of the cache key, so changing voice/provider config doesn't
    # serve stale audio in the old voice.
    voice_hint = (
        settings.elevenlabs_voice_id if provider == "elevenlabs" else languages.get_language(language).bcp47
    )
    key = _cache_key(text, language, provider, voice_hint)

    cached = _cache_get(key)
    if cached is not None:
        return cached, True

    if provider == "google":
        audio, _voice = _synthesize_google(text, language)
    elif provider == "elevenlabs":
        audio, _voice = _synthesize_elevenlabs(text, language)
    else:
        raise TTSUnavailable("not_configured", f"Unknown TTS provider: {provider}")

    _cache_put(key, audio)
    return audio, False
