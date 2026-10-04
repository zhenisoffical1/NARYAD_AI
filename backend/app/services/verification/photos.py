"""Проверка фото: есть ли «после», снято ли во время работ, не повтор ли старого снимка.

Сравнение «до / после» мультимодальной моделью подключается в LLM-шлюзе;
здесь — детерминированная часть, которая работает и без ключа.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Order, Photo
from app.models.enums import OrderType, PhotoKind
from app.services.media import phash_distance
from app.services.verification.facts import CheckResult, CheckStatus

DUPLICATE_DISTANCE = 6  # из 64 бит pHash: ближе — это тот же снимок, пусть и пережатый
SAME_AS_BEFORE_DISTANCE = 4
# Запас на часы телефона: часть аппаратов ещё живёт в старом поясе UTC+6 (до марта 2024)
WINDOW_BEFORE_START = timedelta(minutes=60)
WINDOW_AFTER_DONE = timedelta(minutes=60)
STALE_PHOTO = timedelta(days=1)

LABEL = "Фото до и после"


@dataclass(frozen=True, slots=True)
class PhotoCheck:
    check: CheckResult
    score_1_5: int | None
    confidence: float


def _local(dt: datetime) -> str:
    return dt.astimezone(settings.tz).strftime("%d.%m в %H:%M")


async def check_photos(session: AsyncSession, order: Order) -> PhotoCheck:
    after = [p for p in order.photos if p.kind == PhotoKind.AFTER]
    before = [p for p in order.photos if p.kind == PhotoKind.BEFORE]

    if not after:
        detail = (
            "Фото «после» нет — для внепланового наряда это отмечено в проверке полноты."
            if order.type == OrderType.UNPLANNED
            else "Плановый наряд: фото «после» не требуется."
        )
        return PhotoCheck(CheckResult("photos", LABEL, "skip", detail), None, 1.0)

    items: list[str] = []
    critical = False
    penalty = 0

    # 1. Время съёмки: в окне выполнения работ
    start = (order.started_at or order.issued_at or order.created_at) - WINDOW_BEFORE_START
    end = (order.done_at or order.updated_at) + WINDOW_AFTER_DONE
    for photo in after:
        shot = photo.taken_at or photo.uploaded_at
        if shot < order.created_at - STALE_PHOTO:
            items.append(
                f"Фото «после» снято {_local(shot)} — задолго до выдачи наряда. "
                "Сфотографируйте результат этой работы."
            )
            critical = True
            penalty += 35
        elif not start <= shot <= end:
            items.append(
                f"Фото «после» снято {_local(shot)} — вне времени работ "
                f"({_local(start + WINDOW_BEFORE_START)} — {_local(end - WINDOW_AFTER_DONE)})."
            )
            penalty += 15

    # 2. Не повтор: ни старых снимков из базы, ни фото «до» этого же наряда
    for photo in after:
        if not photo.phash:
            continue
        same_as_before = next(
            (
                b
                for b in before
                if b.phash and phash_distance(photo.phash, b.phash) <= SAME_AS_BEFORE_DISTANCE
            ),
            None,
        )
        if same_as_before:
            items.append(
                "Фото «после» не отличается от фото «до» — по нему не видно результата работы."
            )
            critical = True
            penalty += 35
            continue
        duplicate = await _find_duplicate(session, photo)
        if duplicate is not None:
            number = await session.scalar(
                select(Order.number).where(Order.id == duplicate.order_id)
            )
            items.append(
                f"Фото «после» совпадает со снимком из наряда №{number} "
                f"от {_local(duplicate.uploaded_at)}. Загрузите новое фото результата."
            )
            critical = True
            penalty += 40

    status: CheckStatus
    if critical:
        status = "fail"
    elif items:
        status = "warn"
    else:
        status = "ok"

    if items:
        detail = items[0]
    else:
        compare = (
            "сравнение «до / после» моделью — при подключённом ИИ"
            if before
            else "фото «до» нет — сравнивать не с чем"
        )
        detail = f"Фото «после»: {len(after)}, снято во время работ, повторов нет; {compare}."
    return PhotoCheck(
        CheckResult("photos", LABEL, status, detail, critical, penalty, items), None, 0.9
    )


async def _find_duplicate(session: AsyncSession, photo: Photo) -> Photo | None:
    """Самый похожий снимок из других нарядов. Таблица фото небольшая — сравниваем в Python."""
    others = await session.scalars(
        select(Photo).where(Photo.order_id != photo.order_id, Photo.phash.is_not(None))
    )
    best: Photo | None = None
    best_distance = DUPLICATE_DISTANCE + 1
    for other in others:
        assert other.phash is not None and photo.phash is not None
        distance = phash_distance(photo.phash, other.phash)
        if distance < best_distance:
            best, best_distance = other, distance
    return best
