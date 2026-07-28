"""Speech-to-text for uploaded call/voice snippets.

faster-whisper is open-source and runs on CPU — free, no external API, no
per-request cost. Runs the 'base' model by default — the 'small' model's
~244MB int8 footprint was OOM-crashing the process on Render's 512MB
free-tier instance (loaded alongside FastAPI/supabase/groq/genai already
using ~150-200MB), causing every /scan/audio request to 502. 'base' (~74MB
int8) leaves a safe margin while staying multilingual or Hindi/Gujarati/etc.
"""

import os
import tempfile
from functools import lru_cache

from faster_whisper import WhisperModel

MODEL_SIZE = "base"

# ISO 639-1 codes we support in the product -> Whisper's own language codes
# (Whisper uses the same two-letter codes for these, listed for clarity/guard).
SUPPORTED_WHISPER_LANGUAGES = {
    "en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur",
}


@lru_cache
def _model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe_audio(file_bytes: bytes, language: str) -> str:
    """Writes the upload to a temp file (faster-whisper needs a file path or
    file-like object) and returns the transcribed text, guided by the
    user-selected language for better accuracy on short/ambiguous clips."""
    whisper_language = language if language in SUPPORTED_WHISPER_LANGUAGES else None

    # NamedTemporaryFile keeps an exclusive lock while open on Windows, which
    # blocks faster-whisper/av from opening the same path — write, close, then
    # let it read, and clean up manually instead of relying on the context manager.
    fd, path = tempfile.mkstemp(suffix=".audio")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)

        segments, _info = _model().transcribe(path, language=whisper_language)
        text = " ".join(segment.text.strip() for segment in segments)
    finally:
        os.remove(path)

    return text.strip()
