"""Speech-to-text for uploaded call/voice snippets.

faster-whisper is open-source and runs on CPU — free, no external API, no
per-request cost. Runs the 'small' model by default, which is a reasonable
accuracy/speed tradeoff for a Render free-tier CPU instance; multilingual,
covers Hindi/Gujarati/etc. out of the box.
"""

import os
import tempfile
from functools import lru_cache

from faster_whisper import WhisperModel

MODEL_SIZE = "small"

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
