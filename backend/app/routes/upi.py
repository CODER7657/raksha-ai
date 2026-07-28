from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.services.upi_check import check_upi_or_link

router = APIRouter(prefix="/api", tags=["upi"])


class UpiCheckRequest(BaseModel):
    value: str = Field(min_length=2, max_length=256)


class UpiCheckResponse(BaseModel):
    is_upi: bool
    is_suspicious: bool
    reasons: list[str]


@router.post("/check-upi", response_model=UpiCheckResponse)
def check_upi(payload: UpiCheckRequest, user_id: str = Depends(get_current_user)) -> UpiCheckResponse:
    return UpiCheckResponse(**check_upi_or_link(payload.value))
