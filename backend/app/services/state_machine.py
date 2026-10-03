"""Машина статусов наряда — единственное место, где меняется orders.status.

Таблица переходов — данные, а не if-ы: по ней же строятся подсказки в ошибках
и кнопки следующего действия в интерфейсе.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, Forbidden, Invalid
from app.models import Employee, Order, OrderEvent
from app.models.base import utcnow
from app.models.enums import STATUS_LABELS, TERMINAL_STATUSES, OrderStatus, Role
from app.services.notifications.live import STAFF_ROLES, LiveEvent, queue_event

S = OrderStatus


class Action(StrEnum):
    ACCEPT = "accept"
    QUEUE = "queue"
    REJECT = "reject"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    COMPLETE = "complete"
    BEGIN_REVIEW = "begin_review"
    CLOSE = "close"
    SEND_TO_REWORK = "send_to_rework"
    RESUME_REWORK = "resume_rework"
    REISSUE = "reissue"
    CANCEL = "cancel"


class ActorKind(StrEnum):
    ASSIGNEE = "assignee"
    MASTER = "master"
    SYSTEM = "system"


ACTION_LABELS: dict[Action, str] = {
    Action.ACCEPT: "Принять в работу",
    Action.QUEUE: "Поставить в очередь",
    Action.REJECT: "Отклонить",
    Action.START: "Начать",
    Action.PAUSE: "Приостановить",
    Action.RESUME: "Продолжить",
    Action.COMPLETE: "Исполнено",
    Action.BEGIN_REVIEW: "Отправить на проверку ИИ",
    Action.CLOSE: "Подтвердить закрытие",
    Action.SEND_TO_REWORK: "Вернуть на доработку",
    Action.RESUME_REWORK: "Начать доработку",
    Action.REISSUE: "Переназначить",
    Action.CANCEL: "Отменить наряд",
}

ACTOR_LABELS: dict[ActorKind, str] = {
    ActorKind.ASSIGNEE: "исполнитель наряда",
    ActorKind.MASTER: "мастер",
    ActorKind.SYSTEM: "система",
}

NON_TERMINAL = frozenset(OrderStatus) - TERMINAL_STATUSES


@dataclass(frozen=True, slots=True)
class Transition:
    action: Action
    sources: frozenset[OrderStatus]
    target: OrderStatus
    actors: frozenset[ActorKind]
    reason_required: bool = False


def _t(
    action: Action,
    sources: set[OrderStatus] | frozenset[OrderStatus],
    target: OrderStatus,
    actors: set[ActorKind],
    *,
    reason_required: bool = False,
) -> Transition:
    return Transition(action, frozenset(sources), target, frozenset(actors), reason_required)


A, M, SYS = ActorKind.ASSIGNEE, ActorKind.MASTER, ActorKind.SYSTEM

TRANSITIONS: dict[Action, Transition] = {
    t.action: t
    for t in (
        _t(Action.ACCEPT, {S.ISSUED, S.QUEUED}, S.ACCEPTED, {A}),
        _t(Action.QUEUE, {S.ISSUED}, S.QUEUED, {A}),
        _t(Action.REJECT, {S.ISSUED}, S.REJECTED, {A}, reason_required=True),
        _t(Action.START, {S.ACCEPTED}, S.IN_PROGRESS, {A}),
        _t(Action.PAUSE, {S.IN_PROGRESS}, S.PAUSED, {A}, reason_required=True),
        _t(Action.RESUME, {S.PAUSED}, S.IN_PROGRESS, {A}),
        _t(Action.COMPLETE, {S.IN_PROGRESS}, S.DONE, {A}),
        _t(Action.BEGIN_REVIEW, {S.DONE}, S.AI_REVIEW, {SYS}),
        _t(Action.CLOSE, {S.AI_REVIEW}, S.CLOSED, {M}),
        _t(Action.SEND_TO_REWORK, {S.AI_REVIEW}, S.REWORK, {M, SYS}),
        _t(Action.RESUME_REWORK, {S.REWORK}, S.IN_PROGRESS, {A}),
        _t(Action.REISSUE, {S.REJECTED}, S.ISSUED, {M}),
        _t(Action.CANCEL, NON_TERMINAL, S.CANCELLED, {M}, reason_required=True),
    )
}

# В какое поле наряда пишется время входа в статус
STATUS_TIMESTAMP_FIELD: dict[OrderStatus, str] = {
    S.ISSUED: "issued_at",
    S.QUEUED: "queued_at",
    S.ACCEPTED: "accepted_at",
    S.REJECTED: "rejected_at",
    S.IN_PROGRESS: "started_at",
    S.PAUSED: "paused_at",
    S.DONE: "done_at",
    S.AI_REVIEW: "review_at",
    S.REWORK: "rework_at",
    S.CLOSED: "closed_at",
    S.CANCELLED: "cancelled_at",
}


def available_actions(status: OrderStatus, actor: ActorKind) -> list[Action]:
    """Что этот участник может сделать с нарядом в данном статусе (для кнопок интерфейса)."""
    return [t.action for t in TRANSITIONS.values() if status in t.sources and actor in t.actors]


def check_transition(
    status: OrderStatus,
    action: Action,
    actor: ActorKind,
    *,
    reason: str | None = None,
    number: int | None = None,
) -> Transition:
    """Чистая проверка без БД. Бросает доменную ошибку с понятным текстом."""
    transition = TRANSITIONS[action]
    label = ACTION_LABELS[action]
    order_ref = f"Наряд №{number}" if number is not None else "Наряд"

    if status in TERMINAL_STATUSES:
        raise Conflict(
            f"{order_ref} уже в статусе «{STATUS_LABELS[status]}» — изменить его нельзя. "
            "Если работа нужна снова, выдайте новый наряд."
        )

    if status not in transition.sources:
        possible = available_actions(status, actor)
        hint = (
            "Сейчас доступно: " + ", ".join(f"«{ACTION_LABELS[a]}»" for a in possible) + "."
            if possible
            else "Сейчас ваших действий по нему нет."
        )
        raise Conflict(
            f"Нельзя «{label}»: {order_ref.lower()} в статусе «{STATUS_LABELS[status]}». {hint}"
        )

    if actor not in transition.actors:
        who = " или ".join(ACTOR_LABELS[a] for a in sorted(transition.actors))
        raise Forbidden(f"«{label}» выполняет {who}.")

    if transition.reason_required and not (reason and reason.strip()):
        raise Invalid(f"Укажите причину — без неё нельзя «{label}».")

    return transition


def actor_kind(order: Order, actor: Employee | None) -> ActorKind:
    if actor is None:
        return ActorKind.SYSTEM
    if actor.role in (Role.MASTER, Role.ADMIN):
        return ActorKind.MASTER
    if actor.role == Role.WORKER:
        if order.assignee_id != actor.id:
            raise Forbidden(f"Наряд №{order.number} назначен другому исполнителю.")
        return ActorKind.ASSIGNEE
    raise Forbidden("Руководитель просматривает наряды, но не меняет их статус.")


def _check_completion(order: Order) -> None:
    """Минимум для «Исполнено»; полную форму закрытия проверяет сервис нарядов."""
    missing = []
    if not (order.works_done and order.works_done.strip()):
        missing.append("выполненные работы")
    if order.fault_code_id is None:
        missing.append("шифр неисправности")
    if missing:
        raise Invalid("Чтобы закрыть наряд, заполните: " + ", ".join(missing) + ".")


def order_audience(
    order: Order, *extra_user_ids: int | None
) -> tuple[frozenset[Role], frozenset[int]]:
    """Кому показывать изменения наряда: мастерам и руководству — всё, исполнителю — своё."""
    users = {uid for uid in (order.assignee_id, *extra_user_ids) if uid is not None}
    return STAFF_ROLES, frozenset(users)


async def apply_transition(
    session: AsyncSession,
    order: Order,
    action: Action,
    *,
    actor: Employee | None,
    reason: str | None = None,
    comment: str | None = None,
    data: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> OrderEvent:
    """Проверить и выполнить переход: статус, время, журнал, живое событие.

    Commit делает вызывающий (через commit_and_publish), чтобы переход и связанные
    изменения сохранялись одной транзакцией.
    """
    kind = actor_kind(order, actor)
    transition = check_transition(order.status, action, kind, reason=reason, number=order.number)
    if action == Action.COMPLETE:
        _check_completion(order)

    now = now or utcnow()
    previous = order.status
    order.status = transition.target
    setattr(order, STATUS_TIMESTAMP_FIELD[transition.target], now)
    order.updated_at = now

    event = OrderEvent(
        order_id=order.id,
        actor_id=actor.id if actor else None,
        action=action.value,
        from_status=previous,
        to_status=transition.target,
        reason=reason.strip() if reason else None,
        comment=comment.strip() if comment else None,
        data=data,
        created_at=now,
    )
    session.add(event)

    roles, users = order_audience(order)
    queue_event(
        session,
        LiveEvent(
            type="order.status_changed",
            payload={
                "order_id": order.id,
                "number": order.number,
                "from": previous.value,
                "to": transition.target.value,
                "action": action.value,
                "assignee_id": order.assignee_id,
                "actor_id": actor.id if actor else None,
                "at": now.isoformat(),
            },
            roles=roles,
            user_ids=users,
        ),
    )
    return event
