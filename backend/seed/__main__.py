"""Наполнение базы. Запуск: python -m seed [--scene-only]

Полный сид (по умолчанию): очищает базу, создаёт справочники, историю за 3 месяца
с заложенными закономерностями и демо-сцену текущей смены. Детерминирован (seed=42).
--scene-only: только пересоздать демо-сцену, история не трогается.
"""

import argparse
import asyncio
import time

from app.db import SessionLocal
from app.models.base import utcnow
from seed.demo import build_scene, set_history_end
from seed.history import generate_history
from seed.reference_data import PEOPLE
from seed.world import build_world, wipe


async def full_seed() -> None:
    started = time.perf_counter()
    now = utcnow()
    async with SessionLocal() as session:
        await wipe(session)
        world = await build_world(session)
        history = await generate_history(session, world, now)
        await set_history_end(session, history.history_end)
        scene = await build_scene(session, now)
        await session.commit()

    print(
        f"Справочники: {len(world.equipment)} ед. оборудования, {len(world.faults)} шифров, "
        f"{len(world.materials)} материалов, {len(world.workers)} исполнителей"
    )
    print(
        f"История: {history.orders} нарядов до {history.history_end:%d.%m %H:%M} UTC; "
        f"демо-сцена: {scene} нарядов"
    )
    print(f"Готово за {time.perf_counter() - started:.1f} с.")
    accounts = ", ".join(f"{p.login}/{p.pin}" for p in PEOPLE[:4])
    print(f"Вход: {accounts}; исполнители — фамилия латиницей и ПИН 1234 (akhmetov/1234)")


async def scene_only() -> None:
    async with SessionLocal() as session:
        scene = await build_scene(session)
        await session.commit()
    print(f"Демо-сцена пересоздана: {scene} нарядов")


def main() -> None:
    parser = argparse.ArgumentParser(description="Тестовые данные НарядAI")
    parser.add_argument("--scene-only", action="store_true", help="только демо-сцена")
    args = parser.parse_args()
    asyncio.run(scene_only() if args.scene_only else full_seed())


if __name__ == "__main__":
    main()
