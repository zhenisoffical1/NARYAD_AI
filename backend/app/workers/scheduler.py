"""Фоновый процесс: периодические задачи (контроль сроков, сводки).

Запуск: python -m app.workers.scheduler
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.notifications.bus import bus

log = logging.getLogger("naryadai.scheduler")


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    func: Callable[[], Awaitable[None]]
    seconds: int


JOBS: list[Job] = []


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    scheduler = AsyncIOScheduler(timezone="UTC")
    for job in JOBS:
        scheduler.add_job(
            job.func, "interval", seconds=job.seconds, id=job.name, max_instances=1, coalesce=True
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
