"""Оценка качества ИИ-проверки: 30 размеченных закрытий → точность и матрица ошибок.

Запуск: `python -m tests.ai_eval` (или `make ai-eval`). Без ANTHROPIC_API_KEY работает
mock-режим (правила); с ключом — та же проверка с LLM и сравнением фото моделью.

Каждый случай проходит настоящий путь: наряд в базе, фото через медиасервис (EXIF, pHash),
закрытие, фоновая проверка `run_verification`. Отдельная временная база — рабочие данные
не трогаются. Код возврата 1, если точность ниже 90%.
"""

import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="naryad-ai-eval-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'eval.db').as_posix()}"
os.environ["MEDIA_DIR"] = str(_TMP / "media")
os.environ["DEMO_MODE"] = "false"

import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from datetime import timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import AiAssessment, Base, MaterialWriteoff, Order, Photo  # noqa: E402
from app.models.base import utcnow  # noqa: E402
from app.models.enums import OrderStatus, OrderType, PhotoKind, Priority, Shift  # noqa: E402
from app.services.media import store_photo  # noqa: E402
from app.services.verification.runner import run_verification  # noqa: E402
from seed.world import World, build_world  # noqa: E402
from tests.ai_eval.cases import CASES, Case  # noqa: E402
from tests.ai_eval.images import photo  # noqa: E402

TARGET = 0.9
LABELS = ("accepted", "accepted_with_remarks", "rework", "master")
SHORT = {
    "accepted": "принято",
    "accepted_with_remarks": "замечания",
    "rework": "доработка",
    "master": "мастеру",
}
RESULTS = Path(__file__).parent / "results.json"


async def _add_photo(order: Order, kind: PhotoKind, data: bytes, author_id: int) -> Photo:
    stored = store_photo(data, order.id)
    return Photo(
        order_id=order.id,
        kind=kind,
        path=stored.path,
        thumb_path=stored.thumb_path,
        taken_at=stored.taken_at,
        uploaded_at=utcnow(),
        phash=stored.phash,
        width=stored.width,
        height=stored.height,
        size_bytes=stored.size_bytes,
        author_id=author_id,
    )


async def _make_order(case: Case, index: int, world: World, after_bytes: dict[str, bytes]) -> int:
    """Наряд в «Проверка ИИ» с закрытием и фото, как после нажатия «Исполнено»."""
    master = world.masters[Shift.DAY]
    worker = world.workers[index % len(world.workers)]
    equipment = world.equipment[case.inv]
    fault = world.faults[case.code]
    norm_hours = world.fault_specs[case.code].norm_hours

    done = utcnow() - timedelta(minutes=5)
    started = done - timedelta(hours=float(norm_hours) * case.work_ratio)
    issued = started - timedelta(minutes=10)
    deadline = (
        done - timedelta(minutes=case.late_minutes)
        if case.late_minutes
        else done + timedelta(hours=1)
    )

    async with SessionLocal() as session:
        order = Order(
            number=1000 + index,
            type=OrderType.PLANNED if case.planned else OrderType.UNPLANNED,
            priority=Priority.PLANNED if case.planned else Priority.HIGH,
            status=OrderStatus.AI_REVIEW,
            description=case.description,
            section_id=equipment.section_id,
            equipment_id=equipment.id,
            assignee_id=worker.id,
            master_id=master.id,
            deadline_at=deadline,
            norm_hours=Decimal(str(norm_hours)),
            fault_code_id=fault.id,
            works_done=case.works,
            no_materials=not case.materials,
            created_at=issued,
            issued_at=issued,
            accepted_at=issued + timedelta(minutes=3),
            started_at=started,
            done_at=done,
            review_at=done,
            updated_at=done,
        )
        session.add(order)
        await session.flush()
        for name, qty in case.materials:
            material = world.materials[name]
            session.add(
                MaterialWriteoff(
                    order_id=order.id,
                    material_id=material.id,
                    quantity=Decimal(str(qty)),
                    unit=material.unit,
                )
            )

        before_bytes = None
        if case.before:
            before_bytes = photo(case.before, seed=index * 10 + 1, taken_at=issued)
            session.add(await _add_photo(order, PhotoKind.BEFORE, before_bytes, master.id))

        data: bytes | None
        match case.after:
            case None:
                data = None
            case "dup_of":
                assert case.dup_of is not None
                data = after_bytes[case.dup_of]
            case "same_as_before":
                data = before_bytes
            case "old":
                data = photo("fixed", seed=index * 10 + 2, taken_at=issued - timedelta(days=3))
            case scene:
                data = photo(scene, seed=index * 10 + 2, taken_at=done - timedelta(minutes=3))
        if data is not None:
            after_bytes[case.key] = data
            session.add(await _add_photo(order, PhotoKind.AFTER, data, worker.id))
        await session.commit()
        return order.id


async def _verdict(order_id: int) -> tuple[str, int | None, str]:
    async with SessionLocal() as session:
        a = await session.scalar(
            select(AiAssessment)
            .where(AiAssessment.order_id == order_id)
            .order_by(AiAssessment.id.desc())
        )
        assert a is not None
        verdict = a.verdict.value if a.verdict else "master"
        checks = a.checks or []
        reasons = [
            c["items"][0] if c["items"] else c["detail"]
            for c in checks
            if c["status"] in ("warn", "fail")
        ]
        return verdict, a.score_0_100, reasons[0] if reasons else ""


async def main() -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        world = await build_world(session)
        await session.commit()

    mode = "mock (правила, без ключа)" if settings.llm_mock else f"LLM {settings.llm_model}"
    print(f"НарядAI · оценка ИИ-проверки · {len(CASES)} случаев · режим: {mode}\n")

    after_bytes: dict[str, bytes] = {}
    rows = []
    started = time.monotonic()
    for index, case in enumerate(CASES):
        order_id = await _make_order(case, index, world, after_bytes)
        t0 = time.monotonic()
        await run_verification(order_id)
        seconds = time.monotonic() - t0
        verdict, score, reason = await _verdict(order_id)
        ok = verdict == case.label
        rows.append(
            {
                "key": case.key,
                "label": case.label,
                "verdict": verdict,
                "score": score,
                "ok": ok,
                "vision": case.vision,
                "seconds": round(seconds, 2),
                "reason": reason,
            }
        )
        mark = "ok " if ok else "НЕТ"
        shown = score if score is not None else "—"
        print(
            f"{mark} {case.key:<26} ожидалось: {SHORT[case.label]:<10} "
            f"ИИ: {SHORT[verdict]:<10} {shown:>3}  {reason[:70]}"
        )

    correct = sum(r["ok"] for r in rows)
    accuracy = correct / len(rows)
    print(f"\nТочность вердиктов: {correct}/{len(rows)} = {accuracy:.0%} (цель — {TARGET:.0%})")
    vision_misses = [r["key"] for r in rows if r["vision"] and not r["ok"]]
    if vision_misses:
        print(f"Из ошибок различимы только по фото (нужна модель): {', '.join(vision_misses)}")

    print("\nМатрица ошибок (строки — разметка, столбцы — ответ ИИ):")
    matrix = Counter((r["label"], r["verdict"]) for r in rows)
    print(" " * 12 + "".join(f"{SHORT[c]:>11}" for c in LABELS))
    for label in LABELS[:3]:
        print(f"{SHORT[label]:<12}" + "".join(f"{matrix[(label, c)]:>11}" for c in LABELS))

    slowest = max(r["seconds"] for r in rows)
    print(
        f"\nВремя проверки: в среднем {sum(r['seconds'] for r in rows) / len(rows):.1f} с, "
        f"максимум {slowest:.1f} с (требование — до 15 с); всего {time.monotonic() - started:.0f} с"
    )

    RESULTS.write_text(
        json.dumps(
            {
                "mode": "mock" if settings.llm_mock else settings.llm_model,
                "accuracy": round(accuracy, 3),
                "correct": correct,
                "total": len(rows),
                "cases": rows,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    await engine.dispose()
    return 0 if accuracy >= TARGET else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
