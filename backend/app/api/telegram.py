from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import get_current_user
from app.models import Employee
from app.models.base import utcnow
from app.services.telegram_link import bot_link, make_token

router = APIRouter(prefix="/telegram", tags=["Telegram"])


class TelegramStatus(BaseModel):
    available: bool
    linked: bool
    bot_username: str | None


class TelegramLink(BaseModel):
    url: str
    expires_at: datetime


@router.get("", response_model=TelegramStatus, summary="Подключён ли бот и привязан ли я")
async def status(user: Employee = Depends(get_current_user)) -> TelegramStatus:
    available = bool(settings.telegram_bot_token and settings.telegram_bot_username)
    return TelegramStatus(
        available=available,
        linked=user.telegram_chat_id is not None,
        bot_username=settings.telegram_bot_username if available else None,
    )


@router.post("/link", response_model=TelegramLink, summary="Ссылка для привязки бота")
async def link(user: Employee = Depends(get_current_user)) -> TelegramLink:
    token, expires_at = make_token(user.id, utcnow())
    return TelegramLink(url=bot_link(token), expires_at=expires_at)


@router.delete("/link", status_code=204, summary="Отвязать Telegram")
async def unlink(
    user: Employee = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> None:
    user.telegram_chat_id = None
    await session.commit()
