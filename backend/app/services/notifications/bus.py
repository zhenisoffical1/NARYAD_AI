"""Шина живых событий между процессами.

Бэкенд, бот и планировщик — разные процессы, а WebSocket-соединения живут только в бэкенде.
Поэтому с PostgreSQL события идут через LISTEN/NOTIFY (отдельный брокер не нужен),
а с SQLite (локальный запуск, тесты) — напрямую внутри процесса.
"""

import asyncio
import logging
from typing import Protocol

import asyncpg

from app.config import settings
from app.services.notifications.live import LiveEvent

log = logging.getLogger(__name__)

CHANNEL = "naryad_events"


class EventBus(Protocol):
    async def publish(self, event: LiveEvent) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class LocalBus:
    async def publish(self, event: LiveEvent) -> None:
        from app.ws import manager

        await manager.deliver(event)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class PgBus:
    def __init__(self, database_url: str) -> None:
        self._dsn = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._pool: asyncpg.Pool | None = None
        self._listener: asyncpg.Connection | None = None
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def _get_pool(self) -> asyncpg.Pool:
        # Соединения asyncpg привязаны к циклу событий. Если цикл сменился (тесты, перезапуск
        # приложения в том же процессе), старый пул непригоден — создаём новый в текущем цикле.
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop = loop
            self._pool = None
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)
            return self._pool

    async def publish(self, event: LiveEvent) -> None:
        try:
            pool = await self._get_pool()
            await pool.execute("SELECT pg_notify($1, $2)", CHANNEL, event.to_json())
        except Exception:
            # Живое обновление не должно ломать действие пользователя: данные уже сохранены,
            # клиенты получат их при следующем запросе или переподключении.
            log.exception("Не удалось отправить событие %s", event.type)

    async def start(self) -> None:
        """Слушать канал и раздавать события подключённым WebSocket-клиентам (только бэкенд)."""
        from app.ws import manager

        def on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
            task = asyncio.get_running_loop().create_task(
                manager.deliver(LiveEvent.from_json(payload))
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        self._listener = await asyncpg.connect(self._dsn)
        await self._listener.add_listener(CHANNEL, on_notify)
        log.info("Подписка на канал %s включена", CHANNEL)

    async def stop(self) -> None:
        if self._listener is not None:
            await self._listener.close()
            self._listener = None
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def make_bus() -> EventBus:
    return LocalBus() if settings.is_sqlite else PgBus(settings.database_url)


bus: EventBus = make_bus()
