"""Speech-to-text: the Sarvam -> Groq Whisper ladder and what the audio route says.

No network. `httpx.post` is replaced with a fake that records each call and
answers per provider, so every test states exactly which provider was asked,
with what, and what it said back.

The distinction these tests protect: "a provider heard no speech" (422, the
user's audio is the problem) against "no provider could answer" (503, ours is).
Before Groq replaced the local model the second case could not happen; now both
rungs are network calls, and reporting an outage as "no speech" would send a
user to re-record a clip that was fine.
"""

import asyncio
import io

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.routes import scan
from app.services import llm, stt

SECRET = "gsk_test_SECRET_123"


class Fake:
    """Stands in for httpx.post. `answers` maps a provider to a status and body,
    or to an exception to raise."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, files=None, data=None, timeout=None):
        provider = "groq" if url == stt.GROQ_STT_URL else "sarvam"
        self.calls.append({"provider": provider, "headers": headers, "data": data, "files": files})
        answer = self.answers.get(provider, (500, {"error": "unexpected"}))
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    @property
    def providers(self) -> list[str]:
        return [c["provider"] for c in self.calls]


@pytest.fixture
def keys(monkeypatch):
    """Both keys set, provider on auto. Tests remove what they need absent."""
    monkeypatch.setenv("GROQ_API_KEY", SECRET)
    monkeypatch.setenv("SARVAM_API_KEY", "sarvam-key")
    monkeypatch.setenv("STT_PROVIDER", "auto")
    get_settings.cache_clear()


def use(monkeypatch, fake: Fake) -> Fake:
    monkeypatch.setattr(stt.httpx, "post", fake)
    return fake


# ---------- the ladder ----------

def test_sarvam_answers_first_and_groq_is_not_called(keys, monkeypatch):
    fake = use(monkeypatch, Fake(sarvam=(200, {"transcript": " તમારો OTP "})))
    assert stt.transcribe(b"audio", "gu") == "તમારો OTP"
    assert fake.providers == ["sarvam"]
    assert fake.calls[0]["data"]["language_code"] == "gu-IN"


@pytest.mark.parametrize("sarvam", [(429, {"e": "slow down"}), (402, {"e": "no credit"}),
                                    (500, {"e": "boom"}), httpx.ConnectError("down")])
def test_any_sarvam_failure_falls_to_groq(keys, monkeypatch, sarvam):
    fake = use(monkeypatch, Fake(sarvam=sarvam, groq=(200, {"text": "your OTP"})))
    assert stt.transcribe(b"audio", "en") == "your OTP"
    assert fake.providers == ["sarvam", "groq"]


def test_empty_sarvam_result_still_tries_groq(keys, monkeypatch):
    fake = use(monkeypatch, Fake(sarvam=(200, {"transcript": "  "}), groq=(200, {"text": "hello"})))
    assert stt.transcribe(b"audio", "en") == "hello"
    assert fake.providers == ["sarvam", "groq"]


def test_without_a_sarvam_key_only_groq_is_asked(keys, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY")
    get_settings.cache_clear()
    fake = use(monkeypatch, Fake(groq=(200, {"text": "hi"})))
    assert stt.transcribe(b"audio", "hi") == "hi"
    assert fake.providers == ["groq"]


def test_groq_request_shape(keys, monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "groq")
    get_settings.cache_clear()
    fake = use(monkeypatch, Fake(groq=(200, {"text": "x"})))
    stt.transcribe(b"abc", "gu", filename="clip.ogg", content_type="audio/ogg")
    call = fake.calls[0]
    assert fake.providers == ["groq"]
    assert call["headers"] == {"Authorization": f"Bearer {SECRET}"}
    assert call["data"]["model"] == llm.GROQ_STT_MODEL
    assert call["data"]["language"] == "gu"
    assert call["files"]["file"] == ("clip.ogg", b"abc", "audio/ogg")


def test_odia_is_left_to_whisper_auto_detect(keys, monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "groq")
    get_settings.cache_clear()
    fake = use(monkeypatch, Fake(groq=(200, {"text": "x"})))
    stt.transcribe(b"abc", "or")
    assert "language" not in fake.calls[0]["data"]


def test_old_whisper_setting_means_groq(keys, monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "whisper")
    get_settings.cache_clear()
    assert stt.active_provider() == "groq"


# ---------- when nothing works ----------

def test_both_heard_nothing_is_an_empty_transcript_not_an_error(keys, monkeypatch):
    use(monkeypatch, Fake(sarvam=(200, {"transcript": ""}), groq=(200, {"text": ""})))
    assert stt.transcribe(b"audio", "en") == ""


def test_one_heard_nothing_and_one_failed_is_still_empty(keys, monkeypatch):
    use(monkeypatch, Fake(sarvam=(200, {"transcript": ""}), groq=(503, {"e": "down"})))
    assert stt.transcribe(b"audio", "en") == ""


def test_both_failing_raises_with_the_last_reason(keys, monkeypatch):
    use(monkeypatch, Fake(sarvam=(500, {"e": "x"}), groq=(429, {"e": "y"})))
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(b"audio", "en")
    assert e.value.reason == "rate_limited"


def test_no_keys_at_all_raises_not_configured(keys, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("SARVAM_API_KEY")
    get_settings.cache_clear()
    fake = use(monkeypatch, Fake())
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(b"audio", "en")
    assert e.value.reason == "not_configured"
    assert fake.calls == []


def test_errors_never_carry_the_key(keys, monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "groq")
    get_settings.cache_clear()
    use(monkeypatch, Fake(groq=(401, {"error": f"Invalid API Key {SECRET}"})))
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(b"audio", "en")
    assert e.value.reason == "bad_key"
    assert SECRET not in str(e.value)


def test_network_error_detail_is_the_exception_type_only(keys, monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "groq")
    get_settings.cache_clear()
    use(monkeypatch, Fake(groq=httpx.ConnectError(f"https://x?key={SECRET}")))
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(b"audio", "en")
    assert e.value.reason == "network_error"
    assert SECRET not in str(e.value)


# ---------- the route ----------

def call_route(data: bytes, content_type: str = "audio/webm"):
    upload = UploadFile(file=io.BytesIO(data), filename="clip.webm",
                        headers=Headers({"content-type": content_type}))
    route = scan.scan_audio.__wrapped__  # past the rate limiter, which needs a live request
    return asyncio.run(route(request=None, file=upload, language="en", user_id="u1"))


def test_route_answers_503_when_voice_is_down(monkeypatch):
    def down(*_a, **_k):
        raise stt.STTUnavailable("rate_limited")

    monkeypatch.setattr(scan.stt, "transcribe", down)
    with pytest.raises(HTTPException) as e:
        call_route(b"audio")
    assert e.value.status_code == 503
    assert "type or paste" in e.value.detail


def test_route_answers_422_when_no_speech(monkeypatch):
    monkeypatch.setattr(scan.stt, "transcribe", lambda *_a, **_k: "")
    with pytest.raises(HTTPException) as e:
        call_route(b"audio")
    assert e.value.status_code == 422


def test_route_refuses_audio_over_the_host_limit(monkeypatch):
    monkeypatch.setattr(scan.stt, "transcribe", lambda *_a, **_k: pytest.fail("must not transcribe"))
    with pytest.raises(HTTPException) as e:
        call_route(b"x" * (scan.MAX_AUDIO_BYTES + 1))
    assert e.value.status_code == 413
    assert scan.MAX_AUDIO_BYTES < 4_500_000


def test_route_codec_params_are_ignored_for_the_type_check(monkeypatch):
    monkeypatch.setattr(scan.stt, "transcribe", lambda *_a, **_k: "")
    with pytest.raises(HTTPException) as e:
        call_route(b"audio", "audio/webm;codecs=opus")
    assert e.value.status_code == 422  # got past the 415 check
