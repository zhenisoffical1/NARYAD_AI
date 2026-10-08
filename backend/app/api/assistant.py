from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_role
from app.models import Employee
from app.models.enums import Role
from app.services import assistant, assistant_chat

router = APIRouter(prefix="/assistant", tags=["Ассистент мастера"])
STAFF = require_role(Role.MASTER, Role.BOSS, Role.ADMIN)


class QuestionIn(BaseModel):
    question: str = Field(min_length=2, max_length=400)


class ItemOut(BaseModel):
    title: str
    subtitle: str
    tone: str


class ReplyOut(BaseModel):
    question: str
    intent: str
    text: str
    items: list[ItemOut]
    report: dict[str, Any] | None
    source: str


@router.post("/ask", response_model=ReplyOut, summary="Вопрос ассистенту о смене простым языком")
async def ask(
    body: QuestionIn,
    user: Employee = Depends(STAFF),
    session: AsyncSession = Depends(get_session),
) -> ReplyOut:
    reply = await assistant.ask(session, user, body.question.strip())
    return ReplyOut.model_validate(asdict(reply))


class TurnIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class ChatIn(BaseModel):
    messages: list[TurnIn] = Field(min_length=1, max_length=40)


class ChatOut(BaseModel):
    text: str
    source: str  # llm — ответила модель; rules — ассистент на правилах
    model: str | None
    tools: list[str]
    items: list[dict[str, str]]
    report: dict[str, Any] | None


@router.post(
    "/chat", response_model=ChatOut, summary="Диалог с ИИ-ассистентом (модель + данные смены)"
)
async def chat(
    body: ChatIn,
    user: Employee = Depends(STAFF),
    session: AsyncSession = Depends(get_session),
) -> ChatOut:
    turns = [assistant_chat.Turn(t.role, t.text) for t in body.messages]
    reply = await assistant_chat.chat(session, user, turns)
    return ChatOut.model_validate(asdict(reply))
