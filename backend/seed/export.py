"""Выгрузка тестового набора данных в CSV: python -m seed.export [папка]

Генерирует тот же набор, что `python -m seed` (seed=42), во временной базе в памяти и
сохраняет каждую таблицу в CSV (UTF-8 с BOM, разделитель «;» — открывается в Excel).
Хэши ПИН и идентификаторы Telegram не выгружаются.
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import make_engine
from app.models import Base
from app.models.base import utcnow
from seed.demo import build_scene, set_history_end
from seed.history import generate_history
from seed.world import build_world

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "dataset"
SECRET_COLUMNS = {"pin_hash", "telegram_chat_id"}
SKIP_TABLES = {"alembic_version", "app_state", "llm_calls", "notifications"}


async def export(out_dir: Path) -> dict[str, int]:
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = utcnow()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        world = await build_world(session)
        history = await generate_history(session, world, now)
        await set_history_end(session, history.history_end)
        await build_scene(session, now)
        await session.commit()

    counts: dict[str, int] = {}

    def dump(conn: Connection) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for table in Base.metadata.sorted_tables:
            if table.name in SKIP_TABLES:
                continue
            frame = pd.read_sql_table(table.name, conn)
            frame = frame.drop(columns=[c for c in frame.columns if c in SECRET_COLUMNS])
            frame.to_csv(out_dir / f"{table.name}.csv", sep=";", index=False, encoding="utf-8-sig")
            counts[table.name] = len(frame)

    async with engine.connect() as conn:
        await conn.run_sync(dump)
    await engine.dispose()
    return counts


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    counts = asyncio.run(export(out_dir))
    for name, rows in counts.items():
        print(f"{name:24} {rows:6} строк")
    print(f"Готово: {out_dir}")


if __name__ == "__main__":
    main()
