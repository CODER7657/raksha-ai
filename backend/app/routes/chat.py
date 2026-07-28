from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.rate_limit import limiter
from app.services import chat, rag

router = APIRouter(prefix="/api", tags=["chat"])

LanguageCode = Literal["en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"]

MAX_HISTORY_TURNS = 12


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: LanguageCode = "en"
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().chat_rate_limit)
def send_chat_message(
    request: Request,
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
) -> ChatResponse:
    patterns = rag.retrieve_similar_patterns(payload.message, payload.language)
    context_block = rag.format_context_block(patterns)

    history = [{"role": turn.role, "content": turn.content} for turn in payload.history]

    try:
        reply = chat.chat_reply(payload.message, payload.language, context_block, history)
    except Exception:
        raise HTTPException(status_code=503, detail="Assistant temporarily unavailable — try again in a moment")

    return ChatResponse(reply=reply)
