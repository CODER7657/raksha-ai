from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.supabase_client import get_supabase

router = APIRouter(prefix="/api", tags=["trends"])

CATEGORY_LABELS = {
    "kyc_scam": "KYC update scams",
    "otp_scam": "OTP sharing scams",
    "lottery_scam": "Lottery / prize scams",
    "refund_scam": "Fake refund scams",
    "loan_scam": "Loan app scams",
    "fake_support_scam": "Fake customer care scams",
    "other": "Other scams",
}


class TrendEntry(BaseModel):
    category: str
    label: str
    occurrences: int


@router.get("/trends", response_model=list[TrendEntry])
def get_trends(_user_id: str = Depends(get_current_user)) -> list[TrendEntry]:
    """Real aggregate data — what scam categories are actually being reported
    across all users recently. No message content or user identity is ever
    returned here, just category + count (see get_trending_categories in
    supabase/migrations/0002_categories_and_trends.sql)."""
    supabase = get_supabase()
    try:
        response = supabase.rpc("get_trending_categories", {"days_back": 7, "result_limit": 8}).execute()
    except Exception:
        # An uncaught exception here reaches the browser as a bare, CORS-header-less
        # network failure ("Failed to fetch") instead of a readable error — always
        # convert backend/DB errors into an explicit HTTPException.
        raise HTTPException(status_code=503, detail="Trends temporarily unavailable")
    rows = response.data or []
    return [
        TrendEntry(
            category=row["category"],
            label=CATEGORY_LABELS.get(row["category"], row["category"].replace("_", " ").title()),
            occurrences=row["occurrences"],
        )
        for row in rows
    ]
