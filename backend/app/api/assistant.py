from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_role
from app.models import Employee
from app.models.enums import Role
from app.services import assistant

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
