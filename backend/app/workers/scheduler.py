"""Фоновый процесс: периодические задачи (контроль сроков, сводки).

Запуск: python -m app.workers.scheduler
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import SessionLocal
from app.services.analytics.digest import weekly_digest
from app.services.deadlines import check_deadlines
from app.services.notifications.bus import bus
from app.services.notifications.live import commit_and_publish

log = logging.getLogger("naryadai.scheduler")


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    func: Callable[[], Awaitable[None]]
    seconds: float


async def deadlines_job() -> None:
    async with SessionLocal() as session:
        fired = await check_deadlines(session)
        await commit_and_publish(session)
    for item in fired:
        log.info("Сроки: %s, наряд №%d", item.rule, item.order_number)


JOBS: list[Job] = [Job("deadlines", deadlines_job, settings.deadline_check_seconds)]


async def digest_job() -> None:
    async with SessionLocal() as session:
        count = await weekly_digest(session)
        await commit_and_publish(session)
    log.info("Еженедельная сводка отправлена: %d получателей", count)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    scheduler = AsyncIOScheduler(timezone="UTC")
    for job in JOBS:
        scheduler.add_job(
            job.func, "interval", seconds=job.seconds, id=job.name, max_instances=1, coalesce=True
        )
    # Сводка — по понедельникам в 08:00 по времени предприятия, к началу дневной смены
    scheduler.add_job(
        digest_job,
        "cron",
        day_of_week="mon",
        hour=8,
        timezone=settings.timezone,
        id="weekly_digest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Планировщик запущен, задач: %d", len(JOBS))
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
