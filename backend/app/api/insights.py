"""Подсказки при выдаче, рейтинг, лента уведомлений."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, require_role
from app.errors import NotFound
from app.models import Employee, Notification
from app.models.base import utcnow
from app.models.enums import Role
from app.schemas.common import PersonShort, RefShort
from app.schemas.insights import (
    AssistOut,
    AssistRequest,
    BrigadeRatingOut,
    CandidateOut,
    ComponentOut,
    FaultSuggestionOut,
    MarkRead,
    MyRatingOut,
    NotificationFeed,
    NotificationOut,
    RatingReportOut,
    WorkerRatingOut,
)
from app.services.assist import assist
from app.services.rating import Component, WorkerRating, compute_ratings

router = APIRouter(tags=["Подсказки, рейтинг, уведомления"])
staff_only = require_role(Role.MASTER, Role.BOSS, Role.ADMIN)


@router.post(
    "/orders/assist",
    response_model=AssistOut,
    summary="Подсказки при выдаче: исполнитель, шифр, срок",
)
async def order_assist(
    body: AssistRequest,
    _user: Employee = Depends(require_role(Role.MASTER, Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AssistOut:
    result = await assist(session, body.equipment_id, body.description, body.priority)
    return AssistOut(
        specialty=result.specialty,
        fault_code=(FaultSuggestionOut(**vars(result.fault_code)) if result.fault_code else None),
        order_type=result.order_type,
        deadline_hours=result.deadline_hours,
        candidates=[
            CandidateOut(
                person=c.person,
                specialty=c.specialty,
                grade=c.grade,
                specialty_match=c.specialty_match,
                equipment_score=c.equipment_score,
                reason=c.reason,
                recommended=c.recommended,
            )
            for c in result.candidates
        ],
    )


def _component(c: Component) -> ComponentOut:
    return ComponentOut(
        key=c.key,
        label=c.label,
        weight=c.weight,
        value=round(c.value, 4),
        points=c.points,
        potential=c.potential,
        detail=c.detail,
    )


def _worker(r: WorkerRating) -> WorkerRatingOut:
    return WorkerRatingOut(
        employee=PersonShort.model_validate(r.employee),
        brigade_id=r.employee.brigade_id,
        orders=r.orders,
        score=r.score,
        rank=r.rank,
        components=[_component(c) for c in r.components],
        explanation=r.explanation,
    )


@router.get("/rating", response_model=RatingReportOut, summary="Рейтинг исполнителей и бригад")
async def rating(
    days: int = Query(default=30, ge=1, le=365),
    _user: Employee = Depends(staff_only),
    session: AsyncSession = Depends(get_session),
) -> RatingReportOut:
    report = await compute_ratings(session, days)
    return RatingReportOut(
        period_start=report.start,
        period_end=report.end,
        workers=[_worker(r) for r in report.workers],
        brigades=[
            BrigadeRatingOut(
                brigade=RefShort.model_validate(b.brigade),
                members=b.members,
                orders=b.orders,
                score=b.score,
                components=[_component(c) for c in b.components],
            )
            for b in report.brigades
        ],
    )


@router.get("/rating/me", response_model=MyRatingOut, summary="Мой рейтинг с разбором")
async def my_rating(
    days: int = Query(default=30, ge=1, le=365),
    user: Employee = Depends(require_role(Role.WORKER)),
    session: AsyncSession = Depends(get_session),
) -> MyRatingOut:
    report = await compute_ratings(session, days)
    mine = next((r for r in report.workers if r.employee.id == user.id), None)
    if mine is None:
        raise NotFound("Рейтинг для вас не найден.")
    return MyRatingOut(
        **_worker(mine).model_dump(),
        total_rated=sum(1 for r in report.workers if r.score is not None),
        period_start=report.start,
        period_end=report.end,
    )


@router.get("/notifications", response_model=NotificationFeed, summary="Мои уведомления")
async def notifications(
    limit: int = Query(default=50, ge=1, le=200),
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationFeed:
    items = await session.scalars(
        select(Notification)
        .where(Notification.employee_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.employee_id == user.id, Notification.read_at.is_(None))
    )
    return NotificationFeed(
        items=[NotificationOut.model_validate(n) for n in items], unread=int(unread or 0)
    )


@router.post("/notifications/read", status_code=204, summary="Отметить прочитанными")
async def mark_read(
    body: MarkRead,
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    stmt = (
        update(Notification)
        .where(Notification.employee_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    if body.ids:
        stmt = stmt.where(Notification.id.in_(body.ids))
    await session.execute(stmt)
    await session.commit()
