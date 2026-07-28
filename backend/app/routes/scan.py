import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.supabase_client import get_supabase
from app.rate_limit import limiter
from app.services import llm, rag
from app.services.rule_engine import offline_flag

router = APIRouter(prefix="/api", tags=["scan"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]


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


def _report_to_community_radar(text: str, language: str) -> int:
    """Anonymized aggregate counter — we hash the message, never store raw text here."""
    pattern_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
    supabase = get_supabase()
    response = supabase.rpc(
        "increment_community_report",
        {"p_pattern_hash": pattern_hash, "p_language": language},
    ).execute()
    return response.data if isinstance(response.data, int) else 1


@router.post("/scan/text", response_model=ScanResult)
@limiter.limit(get_settings().scan_rate_limit)
def scan_text(
    request: Request,
    payload: ScanTextRequest,
    user_id: str = Depends(get_current_user),
) -> ScanResult:
    offline_matches = offline_flag(payload.text, payload.language)

    patterns = rag.retrieve_similar_patterns(payload.text, payload.language)
    context_block = rag.format_context_block(patterns)

    try:
        result = llm.classify_message(payload.text, payload.language, context_block)
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

    community_count = _report_to_community_radar(payload.text, payload.language)

    supabase = get_supabase()
    supabase.table("scans").insert(
        {
            "user_id": user_id,
            "input_type": "text",
            "input_text": payload.text,
            "language": payload.language,
            "risk_score": result["risk_score"],
            "verdict": result["verdict"],
            "flagged_phrases": result["flagged_phrases"],
            "explanation": result["explanation"],
            "recommended_action": result["recommended_action"],
        }
    ).execute()

    return ScanResult(
        **result,
        community_report_count=community_count,
        offline_flags_matched=len(offline_matches),
    )


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
