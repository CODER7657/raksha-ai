"""Text-to-speech, proxied through the backend so no API key reaches the browser.

Three providers, selected by config. The ordering of preference exists because
this app's primary languages are Indic, which is exactly where most TTS
services are weakest:

  sarvam (default)
      Built specifically for Indian languages. Covers Gujarati and Odia — Odia
      being a language neither Google nor ElevenLabs speaks at all. Signup
      needs no card and includes one-off free credits, which suits a project
      deployed on a student account.

  google
      Genuine native-speaker neural voices across most Indic languages, and a
      recurring ~1M characters/month free tier. Requires a billing account.
      Note that Studio/Chirp voices are deliberately never auto-selected —
      they cost roughly 10x Wavenet for a tenth of the free quota.

  elevenlabs
      Excellent English voices. On the free plan the Voice Library is blocked,
      leaving only English-native voices, which accept Gujarati text and return
      confident, fluent-sounding audio that is really an English speaker
      reading Gujarati letters. That is worse than an outright failure, because
      it sounds correct to anyone who doesn't speak the language. English-only.

Whatever the provider, every failure raises `TTSUnavailable` so the route can
tell the frontend to fall back to the browser's own voice. Voice is an
enhancement layered over text that's already on screen; it must never become a
hard dependency.

No new dependencies — httpx is already pinned. The Render free tier is 512MB
RAM and has OOM-crashed twice before (see app/services/transcribe.py), so the
cache here is strictly bounded.
"""

import base64
import hashlib
from collections import OrderedDict

from app.core import languages
from app.core.config import get_settings

#: Roughly one long chat reply. Also stays well under every provider's own
#: per-request limit (Sarvam allows 1500 chars on bulbul:v2).
MAX_TTS_CHARS = 800

#: ~50KB per clip, so a few MB at worst.
_CACHE_MAX_ENTRIES = 64

#: key -> (audio_bytes, mime_type)
_audio_cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
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
        if settings.sarvam_api_key:
            return "sarvam"
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


def _cache_get(key: str) -> tuple[bytes, str] | None:
    entry = _audio_cache.get(key)
    if entry is not None:
        _audio_cache.move_to_end(key)  # LRU: refresh recency on hit
    return entry


def _cache_put(key: str, audio: bytes, mime: str) -> None:
    _audio_cache[key] = (audio, mime)
    _audio_cache.move_to_end(key)
    while len(_audio_cache) > _CACHE_MAX_ENTRIES:
        _audio_cache.popitem(last=False)


# --------------------------------------------------------------------------
# Sarvam AI (Indic-specialist)
# --------------------------------------------------------------------------

#: App language code -> Sarvam `language_code`.
#:
#: Mostly "<code>-IN", with one trap: Sarvam spells Odia "od-IN", not the
#: ISO-standard "or-IN" used everywhere else in this codebase. Urdu is absent
#: from Sarvam entirely and so has no entry — it falls back to the browser.
_SARVAM_LANGUAGE_CODES = {
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


def _synthesize_sarvam(text: str, language: str) -> tuple[bytes, str]:
    """Returns (audio_bytes, mime_type)."""
    settings = get_settings()
    api_key = settings.sarvam_api_key
    if not api_key:
        raise TTSUnavailable("not_configured", "SARVAM_API_KEY is not set")

    lang = languages.get_language(language)
    sarvam_code = _SARVAM_LANGUAGE_CODES.get(lang.code)
    if not sarvam_code:
        raise TTSUnavailable("unsupported_language", f"Sarvam has no voice for {lang.english_name}")

    import httpx

    payload: dict = {
        "text": text,
        "language_code": sarvam_code,
        "model": settings.sarvam_model,
        # Sarvam returns WAV unless told otherwise; MP3 keeps responses small
        # over a slow mobile connection.
        "output_audio_codec": "mp3",
        # Slightly slower than default: these are safety instructions, often
        # heard by someone who is panicking.
        "pace": 0.95,
    }
    if settings.sarvam_speaker:
        payload["speaker"] = settings.sarvam_speaker

    try:
        response = httpx.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
    except Exception as exc:
        raise TTSUnavailable("network_error", str(exc)) from exc

    if response.status_code in (401, 403):
        raise TTSUnavailable("bad_key", response.text[:200])
    if response.status_code == 429:
        raise TTSUnavailable("rate_limited", response.text[:200])
    if response.status_code == 402:
        raise TTSUnavailable("quota_or_plan", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    audios = response.json().get("audios") or []
    if not audios:
        raise TTSUnavailable("empty_audio")

    audio = base64.b64decode(audios[0])
    # Trust the bytes over the request: if the codec hint was ignored we'd
    # otherwise hand the browser a WAV labelled as MP3.
    mime = "audio/wav" if audio[:4] == b"RIFF" else "audio/mpeg"
    return audio, mime


# --------------------------------------------------------------------------
# Google Cloud Text-to-Speech
# --------------------------------------------------------------------------

#: Preferred voice families, best-first. Quality AND price both matter here.
#:
#: Neural2 and Wavenet sound natural and share a ~1M characters/month free
#: tier (~$16/1M after). Standard is the cheapest (~4M free, ~$4/1M) and is the
#: safety net for languages that have nothing better — several Indic languages
#: only ship Standard voices.
_GOOGLE_VOICE_TIERS = ("Neural2", "Wavenet", "Standard")

#: Never auto-select these, whatever their quality.
#:
#: Studio is roughly $160 per 1M characters with only ~100K free — about ten
#: times the price of Wavenet for a tenth of the free quota. Chirp3-HD is
#: likewise priced well above Wavenet. Picking either automatically would turn
#: a language gaining a new voice into a surprise bill on someone else's card,
#: with no code change to point at. Opt in deliberately via GOOGLE_TTS_VOICE if
#: you actually want one.
_GOOGLE_VOICE_DENYLIST = ("studio", "chirp")

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

    An explicit GOOGLE_TTS_VOICE overrides all of this.
    """
    settings = get_settings()
    if settings.google_tts_voice:
        return settings.google_tts_voice

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

    if response.status_code in (400, 401, 403):
        raise TTSUnavailable("bad_key", response.text[:200])
    if response.status_code != 200:
        raise TTSUnavailable(f"http_{response.status_code}", response.text[:200])

    voices = response.json().get("voices", [])
    affordable = [
        v
        for v in voices
        if not any(bad in v.get("name", "").lower() for bad in _GOOGLE_VOICE_DENYLIST)
    ]
    if not affordable:
        _google_voice_cache[bcp47] = None
        return None

    best = sorted(affordable, key=lambda v: _google_voice_rank(v.get("name", "")))[0]
    name = best.get("name")
    _google_voice_cache[bcp47] = name
    return name


def _synthesize_google(text: str, language: str) -> tuple[bytes, str]:
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
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.95},
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

    return base64.b64decode(encoded), "audio/mpeg"


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
            ELEVENLABS_TTS_URL.format(voice_id=settings.elevenlabs_voice_id),
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

    return response.content, "audio/mpeg"


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

_PROVIDERS = {
    "sarvam": _synthesize_sarvam,
    "google": _synthesize_google,
    "elevenlabs": _synthesize_elevenlabs,
}


def synthesize(text: str, language: str) -> tuple[bytes, str, bool]:
    """Return (audio_bytes, mime_type, from_cache).

    Raises TTSUnavailable on every failure path so the caller can fall back to
    the browser voice rather than showing the user an error.
    """
    provider = active_provider()
    handler = _PROVIDERS.get(provider)
    if handler is None:
        raise TTSUnavailable("not_configured", f"No TTS provider configured (got {provider!r})")

    text = text.strip()
    if not text:
        raise TTSUnavailable("empty_text")
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    settings = get_settings()
    # Voice is part of the cache key so changing voice/provider config doesn't
    # keep serving audio in the old voice.
    voice_hint = {
        "sarvam": f"{settings.sarvam_model}:{settings.sarvam_speaker}",
        "google": settings.google_tts_voice or "auto",
        "elevenlabs": settings.elevenlabs_voice_id,
    }.get(provider, "")

    key = _cache_key(text, language, provider, voice_hint)
    cached = _cache_get(key)
    if cached is not None:
        audio, mime = cached
        return audio, mime, True

    audio, mime = handler(text, language)
    _cache_put(key, audio, mime)
    return audio, mime, False
