import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_role
from app.models import Equipment, Section
from app.models.enums import Role
from app.services.analytics import Scope, run_detectors
from app.services.analytics.insights import Explained, ask, explain

router = APIRouter(prefix="/analytics", tags=["Аналитика"])

STAFF = require_role(Role.MASTER, Role.BOSS, Role.ADMIN)

# Вывод модели по одному и тому же срезу не меняется минутами — не платим за каждый заход
CACHE_SECONDS = 600
_cache: dict[tuple[int, int | None, int | None], tuple[float, "AnalyticsOut"]] = {}


class InsightOut(BaseModel):
    kind: str
    title: str
    subject: str
    severity: str
    facts: str
    conclusion: str
    recommendation: str
    numbers: dict[str, Any]
    series: list[dict[str, Any]]
    chart: str
    refs: dict[str, int]
    source: str


class AnalyticsOut(BaseModel):
    scope_label: str
    days: int
    section_id: int | None
    equipment_id: int | None
    items: list[InsightOut]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)


class AnswerOut(AnalyticsOut):
    question: str
    source: str


def _out(e: Explained) -> InsightOut:
    f = e.finding
    return InsightOut(
        kind=f.kind,
        title=f.title,
        subject=f.subject,
        severity=f.severity,
        facts=f.facts,
        conclusion=e.conclusion,
        recommendation=e.recommendation,
        numbers=f.numbers,
        series=f.series,
        chart=f.chart,
        refs=f.refs,
        source=e.source,
    )


@router.get("", response_model=AnalyticsOut, summary="Найденные закономерности за период")
async def insights(
    days: int = Query(default=90, ge=7, le=365),
    section_id: int | None = None,
    equipment_id: int | None = None,
    _user: Any = Depends(STAFF),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsOut:
    key = (days, section_id, equipment_id)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    scope = Scope(days=days, section_id=section_id, equipment_id=equipment_id)
    items = await explain(await run_detectors(session, scope))
    if equipment_id is not None:
        equipment = await session.get(Equipment, equipment_id)
        where = equipment.name if equipment else "оборудование"
    elif section_id is not None:
        section = await session.get(Section, section_id)
        where = f"участок «{section.name}»" if section else "участок"
    else:
        where = "всё предприятие"
    result = AnalyticsOut(
        scope_label=f"{where}, {days} дн.",
        days=days,
        section_id=section_id,
        equipment_id=equipment_id,
        items=[_out(i) for i in items],
    )
    _cache[key] = (time.monotonic(), result)
    return result


@router.post("/ask", response_model=AnswerOut, summary="Вопрос к аналитике свободным текстом")
async def ask_question(
    body: AskIn,
    _user: Any = Depends(STAFF),
    session: AsyncSession = Depends(get_session),
) -> AnswerOut:
    answer = await ask(session, body.question.strip())
    return AnswerOut(
        question=answer.question,
        scope_label=answer.scope_label,
        days=answer.days,
        section_id=answer.section_id,
        equipment_id=answer.equipment_id,
        items=[_out(i) for i in answer.items],
        source=answer.source,
    )
