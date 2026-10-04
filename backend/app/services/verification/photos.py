"""Проверка фото: есть ли «после», снято ли во время работ, не повтор ли старого снимка.

Детерминированная часть работает и без ключа; сравнение «до / после» мультимодальной
моделью (`compare_photos`) дополняет её, когда фото «до» есть и критичных проблем не найдено.
"""

import base64
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Order, Photo
from app.models.enums import OrderType, PhotoKind
from app.services.llm import ask_json, image_block, prompt, text_block
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
    source: Literal["llm", "rules"] = "rules"


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
            "сравнение «до / после» моделью недоступно — проверено по правилам"
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


# --- сравнение «до / после» моделью ---------------------------------------------

COMPARE_MAX_SIDE = 1024  # модели хватает, а запрос легче и быстрее
SURE = 0.6  # ниже — наблюдение модели не превращается в замечание


class PhotoCompareOut(BaseModel):
    same_equipment: bool
    problem_fixed: Literal["yes", "no", "unclear"]
    tidy: bool
    issues: list[str]
    score_1_5: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(max_length=400)


def compare_pair(order: Order) -> tuple[Photo, Photo] | None:
    """Первое фото «до» и последнее «после» — что сравнивать моделью."""
    before = [p for p in order.photos if p.kind == PhotoKind.BEFORE]
    after = [p for p in order.photos if p.kind == PhotoKind.AFTER]
    return (before[0], after[-1]) if before and after else None


def _jpeg_base64(rel_path: str) -> str:
    with Image.open(settings.media_dir / rel_path) as source:
        image = source.convert("RGB")
    image.thumbnail((COMPARE_MAX_SIDE, COMPARE_MAX_SIDE))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=82)
    return base64.standard_b64encode(buf.getvalue()).decode()


async def compare_photos(
    base: PhotoCheck, pair: tuple[Photo, Photo], description: str, works: str
) -> PhotoCheck:
    """Дополнить детерминированную проверку оценкой модели. Без модели — base как есть."""
    if base.check.critical:
        return base  # уже ясно, что нужна доработка — тратить вызов незачем
    before, after = pair
    try:
        images = [_jpeg_base64(before.path), _jpeg_base64(after.path)]
    except OSError:
        return base
    out = await ask_json(
        "photo_compare",
        PhotoCompareOut,
        system=prompt("photo_compare"),
        content=[
            text_block("Фото «до»:"),
            image_block(images[0]),
            text_block("Фото «после»:"),
            image_block(images[1]),
            text_block(f"Проблема: {description}\nЧто сделано: {works}"),
        ],
    )
    if out is None:
        return base

    check = base.check
    items = list(check.items)
    critical, penalty = check.critical, check.penalty
    if out.confidence >= SURE:
        if not out.same_equipment:
            items.append("На фото «до» и «после» разное оборудование.")
            critical, penalty = True, penalty + 35
        elif out.problem_fixed == "no":
            items.append("По фото «после» неисправность не устранена.")
            critical, penalty = True, penalty + 30
        if not out.tidy:
            penalty += 10
        items += [i.strip() for i in out.issues if i.strip() and i.strip() not in items]

    status: CheckStatus = "fail" if critical else ("warn" if items else "ok")
    detail = items[0] if items else f"{out.summary.strip()} Оценка по фото: {out.score_1_5} из 5."
    return PhotoCheck(
        CheckResult("photos", LABEL, status, detail, critical, penalty, items),
        out.score_1_5,
        out.confidence,
        source="llm",
    )
