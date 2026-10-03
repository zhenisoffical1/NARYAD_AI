from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import settings


def make_engine(url: str) -> AsyncEngine:
    if not url.startswith("sqlite"):
        return create_async_engine(url, pool_pre_ping=True)

    # SQLite — для запуска без Docker и быстрых тестов. In-memory база живёт
    # в одном соединении, поэтому StaticPool.
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in url:
        kwargs["poolclass"] = StaticPool
    engine = create_async_engine(url, **kwargs)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = make_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
