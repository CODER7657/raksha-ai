import random
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.services.practice_content import category_label, get_round

router = APIRouter(prefix="/api", tags=["practice"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]

MIN_COUNT = 4
MAX_COUNT = 12
DEFAULT_COUNT = 8


class PracticeQuestion(BaseModel):
    id: str
    text: str
    is_scam: bool
    category: str
    category_label: str
    red_flags: list[str]
    tip: str


class PracticeRound(BaseModel):
    language: str
    questions: list[PracticeQuestion]


@router.get("/practice/round", response_model=PracticeRound)
def get_practice_round(
    language: LanguageCode = "en",
    count: int = DEFAULT_COUNT,
    user_id: str = Depends(get_current_user),
) -> PracticeRound:
    clamped_count = max(MIN_COUNT, min(MAX_COUNT, count))
    pool = get_round(language, clamped_count)
    sample = random.sample(pool, k=min(clamped_count, len(pool)))
    random.shuffle(sample)

    return PracticeRound(
        language=language,
        questions=[
            PracticeQuestion(
                id=item.id,
                text=item.text,
                is_scam=item.is_scam,
                category=item.category,
                category_label=category_label(item.category, language),
                red_flags=item.red_flags,
                tip=item.tip,
            )
            for item in sample
        ],
    )
