from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.rate_limit import limiter
from app.services import chat

router = APIRouter(prefix="/api", tags=["chat"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: LanguageCode = "en"
    # Client-held conversation so far — backend is stateless, doesn't
    # persist chat history anywhere.
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("15/minute")
def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    _user_id: str = Depends(get_current_user),
) -> ChatResponse:
    try:
        reply = chat.answer(
            payload.message,
            payload.language,
            [m.model_dump() for m in payload.history],
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Chat assistant temporarily unavailable")

    return ChatResponse(reply=reply)
