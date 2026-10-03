from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session

router = APIRouter(tags=["Служебное"])


@router.get("/health", summary="Проверка работоспособности")
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    body = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "unavailable",
        "llm": "mock" if settings.llm_mock else "anthropic",
        "telegram": "on" if settings.telegram_bot_token else "off",
        "demo_mode": settings.demo_mode,
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)
