import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.supabase_client import get_supabase
from app.rate_limit import limiter
from app.services import llm, rag
from app.services.rule_engine import offline_flag
from app.services.transcribe import transcribe_audio

router = APIRouter(prefix="/api", tags=["scan"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB — plenty for a short call snippet, caps abuse
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg",
}


class ScanTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: LanguageCode = "en"


class ScanResult(BaseModel):
    risk_score: int
    verdict: str
    flagged_phrases: list[str]
    explanation: str
    recommended_action: str
    community_report_count: int
    offline_flags_matched: int
    transcript: str | None = None


def _report_to_community_radar(text: str, language: str) -> int:
    """Anonymized aggregate counter — we hash the message, never store raw text here."""
    pattern_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
    supabase = get_supabase()
    response = supabase.rpc(
        "increment_community_report",
        {"p_pattern_hash": pattern_hash, "p_language": language},
    ).execute()
    return response.data if isinstance(response.data, int) else 1


def _run_scan_pipeline(text: str, language: str, input_type: str, user_id: str) -> dict:
    """Shared by both /scan/text and /scan/audio once we have plain text in
    hand — same RAG retrieval + LLM classification + offline fallback +
    persistence for either input type."""
    offline_matches = offline_flag(text, language)

    patterns = rag.retrieve_similar_patterns(text, language)
    context_block = rag.format_context_block(patterns)

    try:
        result = llm.classify_message(text, language, context_block)
    except Exception:
        if offline_matches:
            result = {
                "risk_score": 70,
                "verdict": "suspicious",
                "flagged_phrases": offline_matches,
                "explanation": "AI service unavailable — flagged by offline pattern rules as a precaution.",
                "recommended_action": "Do not share OTP/personal details. Verify with the official app/helpline before acting.",
            }
        else:
            raise HTTPException(status_code=503, detail="Detection service temporarily unavailable")

    community_count = _report_to_community_radar(text, language)

    supabase = get_supabase()
    supabase.table("scans").insert(
        {
            "user_id": user_id,
            "input_type": input_type,
            "input_text": text,
            "language": language,
            "risk_score": result["risk_score"],
            "verdict": result["verdict"],
            "flagged_phrases": result["flagged_phrases"],
            "explanation": result["explanation"],
            "recommended_action": result["recommended_action"],
        }
    ).execute()

    return {
        **result,
        "community_report_count": community_count,
        "offline_flags_matched": len(offline_matches),
    }


@router.post("/scan/text", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
def scan_text(
    request: Request,
    payload: ScanTextRequest,
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    result = _run_scan_pipeline(payload.text, payload.language, "text", user_id)
    return ScanResult(**result)


@router.post("/scan/audio", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
async def scan_audio(
    request: Request,
    file: UploadFile,
    language: LanguageCode = "en",
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    # Browser-recorded audio (MediaRecorder) sends a content-type with codec
    # params, e.g. "audio/webm;codecs=opus" — compare on the base MIME type only.
    base_content_type = (file.content_type or "").split(";", 1)[0].strip()
    if base_content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {file.content_type}")

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (10MB limit)")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcript = transcribe_audio(audio_bytes, language)
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe any speech from the audio")

    result = _run_scan_pipeline(transcript, language, "audio", user_id)
    return ScanResult(**result, transcript=transcript)


@router.get("/history")
def get_history(user_id: str = Depends(get_current_user)) -> list[dict]:
    supabase = get_supabase()
    response = (
        supabase.table("scans")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []
