"""Наряды: выдача, чтение, действия, закрытие, фото. Статус меняет только state_machine."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.errors import Conflict, Forbidden, Invalid, NotFound
from app.models import (
    AiAssessment,
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    Material,
    MaterialWriteoff,
    Order,
    OrderEvent,
    Photo,
)
from app.models.base import utcnow
from app.models.enums import (
    ACTIVE_STATUSES,
    DEADLINE_TRACKED_STATUSES,
    PRE_DONE_STATUSES,
    PRIORITY_LABELS,
    PRIORITY_RANK,
    STATUS_LABELS,
    AssessmentStatus,
    OrderStatus,
    OrderType,
    PhotoKind,
    Priority,
    Role,
)
from app.schemas.orders import (
    ActionRequest,
    AssessmentOut,
    CompleteRequest,
    EventOut,
    OrderCreate,
    OrderDetail,
    OrderListItem,
    OverrideRequest,
    PhotoOut,
    PriorityRequest,
    ReassignRequest,
    WriteoffOut,
)
from app.services.media import delete_files, media_url, store_photo
from app.services.notifications.live import STAFF_ROLES, LiveEvent, queue_event
from app.services.notifications.notify import notify
from app.services.state_machine import (
    Action,
    ActorKind,
    actor_kind,
    apply_transition,
    available_actions,
    check_transition,
    reassign,
)

S = OrderStatus

LIST_LOAD = (
    selectinload(Order.equipment),
    selectinload(Order.section),
    selectinload(Order.assignee),
    selectinload(Order.master),
)
DETAIL_LOAD = (
    *LIST_LOAD,
    selectinload(Order.events).selectinload(OrderEvent.actor),
    selectinload(Order.photos),
    selectinload(Order.writeoffs).selectinload(MaterialWriteoff.material),
    selectinload(Order.fault_code),
)

# Действия, доступные через POST /orders/{id}/actions/{action}
HTTP_ACTIONS = frozenset(
    {
        Action.ACCEPT,
        Action.QUEUE,
        Action.REJECT,
        Action.START,
        Action.PAUSE,
        Action.RESUME,
        Action.RESUME_REWORK,
        Action.CLOSE,
        Action.SEND_TO_REWORK,
        Action.CANCEL,
    }
)


def default_deadline_hours(priority: Priority, norm_hours: Decimal | None = None) -> float:
    """Срок по приоритету, но не меньше норматива работ с запасом 25%."""
    by_priority = {
        Priority.EMERGENCY: settings.deadline_hours_emergency,
        Priority.HIGH: settings.deadline_hours_high,
        Priority.NORMAL: settings.deadline_hours_normal,
        Priority.PLANNED: settings.deadline_hours_planned,
    }[priority]
    if norm_hours is None:
        return by_priority
    return max(by_priority, float(norm_hours) * 1.25)


# --- чтение -------------------------------------------------------------------


def overdue_minutes(order: Order, now: datetime) -> int:
    if order.status not in DEADLINE_TRACKED_STATUSES or now <= order.deadline_at:
        return 0
    return int((now - order.deadline_at).total_seconds() // 60)


def local_time(dt: datetime) -> str:
    return dt.astimezone(settings.tz).strftime("%H:%M")


def local_datetime(dt: datetime) -> str:
    return dt.astimezone(settings.tz).strftime("%d.%m %H:%M")


async def load_order(session: AsyncSession, order_id: int, *, detail: bool = False) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(*(DETAIL_LOAD if detail else LIST_LOAD))
        .execution_options(populate_existing=True)
    )
    order = await session.scalar(stmt)
    if order is None:
        raise NotFound(f"Наряд с id {order_id} не найден. Возможно, его удалили из демо-сцены.")
    return order


def ensure_can_view(order: Order, user: Employee) -> None:
    if user.role != Role.WORKER:
        return
    if order.assignee_id == user.id:
        return
    if order.assignee_id is None and order.brigade_id and order.brigade_id == user.brigade_id:
        return
    raise Forbidden(f"Наряд №{order.number} назначен другому исполнителю.")


async def latest_assessments(
    session: AsyncSession, order_ids: Sequence[int]
) -> dict[int, AiAssessment]:
    if not order_ids:
        return {}
    newest = (
        select(AiAssessment.order_id, func.max(AiAssessment.id).label("id"))
        .where(AiAssessment.order_id.in_(order_ids))
        .group_by(AiAssessment.order_id)
        .subquery()
    )
    rows = await session.scalars(select(AiAssessment).join(newest, AiAssessment.id == newest.c.id))
    return {a.order_id: a for a in rows}


def to_list_item(order: Order, assessment: AiAssessment | None, now: datetime) -> OrderListItem:
    item = OrderListItem.model_validate(order)
    minutes = overdue_minutes(order, now)
    item.is_overdue = minutes > 0
    item.overdue_minutes = minutes
    if assessment is not None and assessment.status == AssessmentStatus.DONE:
        item.ai_score = assessment.final_score
        item.ai_verdict = assessment.verdict
    return item


def photo_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        kind=photo.kind,
        url=media_url(photo.path),
        thumb_url=media_url(photo.thumb_path),
        taken_at=photo.taken_at,
        uploaded_at=photo.uploaded_at,
        author_id=photo.author_id,
    )


def user_actions(order: Order, user: Employee) -> list[str]:
    """Кнопки, которые этот пользователь может нажать по наряду сейчас."""
    try:
        kind = actor_kind(order, user)
    except Forbidden:
        return []
    actions = [a.value for a in available_actions(order.status, kind) if a in HTTP_ACTIONS]
    if kind == ActorKind.ASSIGNEE and order.status == S.IN_PROGRESS:
        actions.append(Action.COMPLETE.value)
    if kind == ActorKind.MASTER and order.status in PRE_DONE_STATUSES:
        actions += ["reassign", "change_priority"]
    return actions


async def order_detail(session: AsyncSession, order_id: int, user: Employee) -> OrderDetail:
    order = await load_order(session, order_id, detail=True)
    ensure_can_view(order, user)
    assessment = (await latest_assessments(session, [order.id])).get(order.id)
    now = utcnow()
    base = to_list_item(order, assessment, now)

    assessment_out = AssessmentOut.model_validate(assessment) if assessment else None
    if assessment_out and user.role == Role.WORKER:
        assessment_out.explanation_master = None

    actions = user_actions(order, user)
    if assessment and user.role in (Role.MASTER, Role.ADMIN):
        actions.append("override_assessment")

    return OrderDetail(
        **base.model_dump(),
        comment=order.comment,
        norm_hours=order.norm_hours,
        fault_code=order.fault_code,
        works_done=order.works_done,
        no_materials=order.no_materials,
        closing_comment=order.closing_comment,
        downtime_minutes=order.downtime_minutes,
        events=[EventOut.model_validate(e) for e in order.events],
        photos=[photo_out(p) for p in order.photos],
        materials=[
            WriteoffOut(
                material_id=w.material_id, name=w.material.name, quantity=w.quantity, unit=w.unit
            )
            for w in order.writeoffs
        ],
        assessment=assessment_out,
        actions=actions,
    )


@dataclass
class OrderFilters:
    statuses: list[OrderStatus] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)
    active: bool | None = None
    overdue: bool | None = None
    section_id: int | None = None
    equipment_id: int | None = None
    assignee_id: int | None = None
    brigade_id: int | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    q: str | None = None
    sort: str = "recent"  # recent | urgency
    limit: int = 200
    offset: int = 0


def _filtered(stmt: Select[Order], f: OrderFilters, now: datetime) -> Select[Order]:
    if f.statuses:
        stmt = stmt.where(Order.status.in_(f.statuses))
    if f.priorities:
        stmt = stmt.where(Order.priority.in_(f.priorities))
    if f.active is True:
        stmt = stmt.where(Order.status.in_(ACTIVE_STATUSES))
    if f.overdue is True:
        stmt = stmt.where(Order.status.in_(DEADLINE_TRACKED_STATUSES), Order.deadline_at < now)
    for column, value in (
        (Order.section_id, f.section_id),
        (Order.equipment_id, f.equipment_id),
        (Order.assignee_id, f.assignee_id),
        (Order.brigade_id, f.brigade_id),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if f.created_from:
        stmt = stmt.where(Order.created_at >= f.created_from)
    if f.created_to:
        stmt = stmt.where(Order.created_at < f.created_to)
    if f.q:
        text = f.q.strip().lstrip("№")
        if text.isdigit():
            stmt = stmt.where(Order.number == int(text))
        else:
            stmt = stmt.where(Order.description.ilike(f"%{text}%"))
    return stmt


async def list_orders(
    session: AsyncSession, user: Employee, filters: OrderFilters
) -> list[OrderListItem]:
    now = utcnow()
    stmt = _filtered(select(Order).options(*LIST_LOAD), filters, now)
    if user.role == Role.WORKER:
        stmt = stmt.where(
            or_(
                Order.assignee_id == user.id,
                (Order.assignee_id.is_(None))
                & (Order.brigade_id == user.brigade_id)
                & (Order.status == S.ISSUED),
            )
        )
    stmt = stmt.order_by(Order.created_at.desc()).limit(filters.limit).offset(filters.offset)
    orders = list((await session.scalars(stmt)).all())

    if filters.sort == "urgency":
        orders.sort(key=lambda o: (PRIORITY_RANK[o.priority], o.deadline_at))

    assessments = await latest_assessments(session, [o.id for o in orders])
    return [to_list_item(o, assessments.get(o.id), now) for o in orders]


# --- выдача -------------------------------------------------------------------


async def _next_number(session: AsyncSession) -> int:
    current = await session.scalar(select(func.max(Order.number)))
    return (current or 0) + 1


async def active_worker(session: AsyncSession, employee_id: int) -> Employee:
    worker = await session.get(Employee, employee_id)
    if worker is None or not worker.is_active or worker.role != Role.WORKER:
        raise Invalid("Исполнитель не найден среди сотрудников. Выберите из списка смены.")
    return worker


def _brigade_member_ids(members: Sequence[Employee]) -> frozenset[int]:
    return frozenset(m.id for m in members)


async def create_order(
    session: AsyncSession, data: OrderCreate, master: Employee, now: datetime | None = None
) -> Order:
    now = now or utcnow()
    equipment = await session.get(Equipment, data.equipment_id)
    if equipment is None:
        raise Invalid("Оборудование не найдено в справочнике. Выберите из списка.")

    assignee = await active_worker(session, data.assignee_id) if data.assignee_id else None
    brigade_members: list[Employee] = []
    if data.brigade_id is not None:
        if await session.get(Brigade, data.brigade_id) is None:
            raise Invalid("Бригада не найдена.")
        if assignee is None:
            brigade_members = list(
                await session.scalars(
                    select(Employee).where(
                        Employee.brigade_id == data.brigade_id,
                        Employee.role == Role.WORKER,
                        Employee.is_active.is_(True),
                    )
                )
            )

    norm_hours = data.norm_hours
    if data.fault_code_id is not None:
        fault = await session.scalar(
            select(FaultCode)
            .where(FaultCode.id == data.fault_code_id)
            .options(selectinload(FaultCode.norm))
        )
        if fault is None:
            raise Invalid("Шифр неисправности не найден.")
        if norm_hours is None and fault.norm is not None:
            norm_hours = fault.norm.norm_hours

    if data.deadline_at is not None:
        if data.deadline_at <= now:
            raise Invalid("Срок уже прошёл. Укажите время в будущем.")
        deadline = data.deadline_at
    else:
        deadline = now + timedelta(hours=default_deadline_hours(data.priority, norm_hours))

    order_type = data.type or (
        OrderType.PLANNED if data.priority == Priority.PLANNED else OrderType.UNPLANNED
    )
    stopped = (
        data.equipment_stopped
        if data.equipment_stopped is not None
        else data.priority == Priority.EMERGENCY
    )

    order = Order(
        number=await _next_number(session),
        type=order_type,
        priority=data.priority,
        status=S.ISSUED,
        description=data.description.strip(),
        comment=data.comment.strip() if data.comment else None,
        section_id=equipment.section_id,
        equipment_id=equipment.id,
        assignee_id=assignee.id if assignee else None,
        # Бригада запоминается и для личного наряда — нужна для рейтинга бригад
        brigade_id=data.brigade_id or (assignee.brigade_id if assignee else None),
        master_id=master.id,
        deadline_at=deadline,
        norm_hours=norm_hours,
        fault_code_id=data.fault_code_id,
        equipment_stopped=stopped,
        created_at=now,
        issued_at=now,
        updated_at=now,
    )
    session.add(order)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "Номер наряда занял одновременный запрос. Нажмите «Выдать» ещё раз."
        ) from exc

    session.add(
        OrderEvent(
            order_id=order.id,
            actor_id=master.id,
            action="create",
            from_status=None,
            to_status=S.ISSUED,
            comment=order.comment,
            data={"priority": data.priority.value, "deadline_at": deadline.isoformat()},
            created_at=now,
        )
    )

    recipients = {assignee.id} if assignee else set(_brigade_member_ids(brigade_members))
    queue_event(
        session,
        LiveEvent(
            type="order.created",
            payload={
                "order_id": order.id,
                "number": order.number,
                "priority": order.priority.value,
                "assignee_id": order.assignee_id,
            },
            roles=STAFF_ROLES,
            user_ids=frozenset(recipients),
        ),
    )

    urgent = data.priority == Priority.EMERGENCY
    title = f"Новый наряд №{order.number}" + (" — АВАРИЙНЫЙ" if urgent else "")
    body = (
        f"{equipment.name} ({equipment.inv_number}). {order.description[:160]}\n"
        f"Приоритет: {PRIORITY_LABELS[data.priority].lower()}. Срок: {local_datetime(deadline)}."
    )
    for employee_id in recipients:
        await notify(
            session,
            employee_id=employee_id,
            kind="order_new",
            title=title,
            body=body,
            order_id=order.id,
            urgent=urgent,
        )
    return order


# --- действия -----------------------------------------------------------------


async def perform_action(
    session: AsyncSession, order: Order, action: Action, user: Employee, req: ActionRequest
) -> None:
    if action not in HTTP_ACTIONS:
        raise NotFound("Такого действия нет.")
    await apply_transition(
        session, order, action, actor=user, reason=req.reason, comment=req.comment
    )

    reason = f": {req.reason.strip()}" if req.reason and req.reason.strip() else ""
    if action in (Action.REJECT, Action.PAUSE):
        verb = "отклонён" if action == Action.REJECT else "приостановлен"
        await notify(
            session,
            employee_id=order.master_id,
            kind=f"order_{action.value}",
            title=f"Наряд №{order.number} {verb}",
            body=f"{user.short_name}{reason}",
            order_id=order.id,
        )
    elif action in (Action.SEND_TO_REWORK, Action.CLOSE, Action.CANCEL) and order.assignee_id:
        text = {
            Action.SEND_TO_REWORK: ("возвращён на доработку", "order_rework"),
            Action.CLOSE: ("закрыт мастером", "order_closed"),
            Action.CANCEL: ("отменён", "order_cancelled"),
        }[action]
        comment = f" {req.comment.strip()}" if req.comment and req.comment.strip() else ""
        await notify(
            session,
            employee_id=order.assignee_id,
            kind=text[1],
            title=f"Наряд №{order.number} {text[0]}",
            body=f"{user.short_name}{reason}.{comment}".strip(),
            order_id=order.id,
        )


async def complete_order(
    session: AsyncSession,
    order: Order,
    user: Employee,
    req: CompleteRequest,
    now: datetime | None = None,
) -> None:
    """Форма закрытия → «Исполнено» → сразу «Проверка ИИ»."""
    now = now or utcnow()
    kind = actor_kind(order, user)
    check_transition(order.status, Action.COMPLETE, kind, number=order.number)

    if await session.get(FaultCode, req.fault_code_id) is None:
        raise Invalid("Шифр неисправности не найден в справочнике.")
    if req.no_materials and req.materials:
        raise Invalid("Отмечено «Без материалов», но материалы указаны. Уберите одно из двух.")
    if not req.no_materials and not req.materials:
        raise Invalid("Укажите списанные материалы или отметьте «Без материалов».")

    material_ids = [m.material_id for m in req.materials]
    if len(set(material_ids)) != len(material_ids):
        raise Invalid("Один материал указан дважды. Сложите количество в одну строку.")
    materials = {
        m.id: m
        for m in await session.scalars(select(Material).where(Material.id.in_(material_ids)))
    }
    if missing := set(material_ids) - materials.keys():
        raise Invalid(f"Материалы не найдены в справочнике: {sorted(missing)}.")

    if order.type == OrderType.UNPLANNED:
        after = await session.scalar(
            select(func.count())
            .select_from(Photo)
            .where(Photo.order_id == order.id, Photo.kind == PhotoKind.AFTER)
        )
        if not after:
            raise Invalid(
                "Для внепланового наряда нужно фото «после». Сфотографируйте результат работы."
            )

    order.works_done = req.works_done.strip()
    order.fault_code_id = req.fault_code_id
    order.no_materials = req.no_materials
    order.closing_comment = req.comment.strip() if req.comment else None
    await session.execute(delete(MaterialWriteoff).where(MaterialWriteoff.order_id == order.id))
    for line in req.materials:
        session.add(
            MaterialWriteoff(
                order_id=order.id,
                material_id=line.material_id,
                quantity=line.quantity,
                unit=materials[line.material_id].unit,
            )
        )
    if order.equipment_stopped:
        order.downtime_minutes = int((now - order.created_at).total_seconds() // 60)

    await apply_transition(
        session,
        order,
        Action.COMPLETE,
        actor=user,
        comment=req.comment,
        data={"materials": len(req.materials), "no_materials": req.no_materials},
        now=now,
    )
    await apply_transition(session, order, Action.BEGIN_REVIEW, actor=None, now=now)
    await notify(
        session,
        employee_id=order.master_id,
        kind="order_done",
        title=f"Наряд №{order.number} исполнен",
        body=f"{user.short_name}. ИИ проверяет закрытие — результат через несколько секунд.",
        order_id=order.id,
    )


async def reassign_order(
    session: AsyncSession, order: Order, user: Employee, req: ReassignRequest
) -> None:
    new_assignee = await active_worker(session, req.assignee_id)
    previous = order.assignee_id
    await reassign(session, order, new_assignee, actor=user, comment=req.comment)
    await notify(
        session,
        employee_id=new_assignee.id,
        kind="order_new",
        title=f"Вам передан наряд №{order.number}",
        body=order.description[:200],
        order_id=order.id,
        urgent=order.priority == Priority.EMERGENCY,
    )
    if previous and previous != new_assignee.id:
        await notify(
            session,
            employee_id=previous,
            kind="order_reassigned",
            title=f"Наряд №{order.number} передан другому исполнителю",
            body=req.comment or "Мастер переназначил наряд.",
            order_id=order.id,
        )


def _ensure_master(user: Employee) -> None:
    if user.role not in (Role.MASTER, Role.ADMIN):
        raise Forbidden("Это действие выполняет мастер.")


def _order_updated(session: AsyncSession, order: Order, change: str, *extra: int | None) -> None:
    users = {uid for uid in (order.assignee_id, *extra) if uid is not None}
    queue_event(
        session,
        LiveEvent(
            type="order.updated",
            payload={"order_id": order.id, "number": order.number, "change": change},
            roles=STAFF_ROLES,
            user_ids=frozenset(users),
        ),
    )


async def change_priority(
    session: AsyncSession, order: Order, user: Employee, req: PriorityRequest
) -> None:
    _ensure_master(user)
    if order.status not in PRE_DONE_STATUSES:
        raise Conflict(
            f"Приоритет меняется только до «Исполнено». Наряд №{order.number} "
            f"в статусе «{STATUS_LABELS[order.status]}»."
        )
    if req.priority == order.priority:
        raise Invalid("У наряда уже такой приоритет.")
    previous = order.priority
    order.priority = req.priority
    now = utcnow()
    order.updated_at = now
    session.add(
        OrderEvent(
            order_id=order.id,
            actor_id=user.id,
            action="priority_changed",
            comment=req.comment,
            data={"from": previous.value, "to": req.priority.value},
            created_at=now,
        )
    )
    _order_updated(session, order, "priority")
    if order.assignee_id and PRIORITY_RANK[req.priority] < PRIORITY_RANK[previous]:
        urgent = req.priority == Priority.EMERGENCY
        await notify(
            session,
            employee_id=order.assignee_id,
            kind="order_priority",
            title=f"Наряд №{order.number}: приоритет повышен до «{PRIORITY_LABELS[req.priority]}»",
            body=req.comment or "Мастер поднял приоритет — возьмите наряд раньше остальных.",
            order_id=order.id,
            urgent=urgent,
        )


async def override_assessment(
    session: AsyncSession, order: Order, user: Employee, req: OverrideRequest
) -> None:
    _ensure_master(user)
    assessment = (await latest_assessments(session, [order.id])).get(order.id)
    if assessment is None or assessment.status != AssessmentStatus.DONE:
        raise Conflict("Оценки ИИ по этому наряду ещё нет — изменить нечего.")
    previous = assessment.final_score
    assessment.master_override_score = req.score
    assessment.master_comment = req.comment.strip()
    assessment.master_id = user.id
    session.add(
        OrderEvent(
            order_id=order.id,
            actor_id=user.id,
            action="assessment_overridden",
            comment=req.comment,
            data={"from": previous, "to": req.score},
            created_at=utcnow(),
        )
    )
    _order_updated(session, order, "assessment")
    if order.assignee_id:
        await notify(
            session,
            employee_id=order.assignee_id,
            kind="assessment_overridden",
            title=f"Наряд №{order.number}: мастер изменил оценку — {req.score} баллов",
            body=req.comment,
            order_id=order.id,
        )


# --- фото ---------------------------------------------------------------------

AFTER_PHOTO_STATUSES = frozenset({S.IN_PROGRESS, S.PAUSED, S.REWORK})


async def add_photos(
    session: AsyncSession,
    order: Order,
    user: Employee,
    kind: PhotoKind,
    files: list[bytes],
) -> list[Photo]:
    if kind == PhotoKind.BEFORE:
        _ensure_master(user)
        if order.status not in PRE_DONE_STATUSES:
            raise Conflict("Фото неисправности добавляют до «Исполнено».")
    else:
        if actor_kind(order, user) != ActorKind.ASSIGNEE:
            raise Forbidden("Фото «после» прикладывает исполнитель наряда.")
        if order.status not in AFTER_PHOTO_STATUSES:
            raise Conflict("Фото «после» прикладывают, пока наряд в работе.")

    if not files:
        raise Invalid("Выберите хотя бы одно фото.")
    existing = await session.scalar(
        select(func.count())
        .select_from(Photo)
        .where(Photo.order_id == order.id, Photo.kind == kind)
    )
    limit = settings.max_photos_per_kind
    label = "до" if kind == PhotoKind.BEFORE else "после"
    if (existing or 0) + len(files) > limit:
        raise Invalid(
            f"Можно приложить не больше {limit} фото «{label}». Уже есть {existing}. "
            "Удалите лишние или выберите меньше."
        )

    stored = await asyncio.gather(*(asyncio.to_thread(store_photo, f, order.id) for f in files))
    now = utcnow()
    photos = [
        Photo(
            order_id=order.id,
            kind=kind,
            path=s.path,
            thumb_path=s.thumb_path,
            taken_at=s.taken_at,
            uploaded_at=now,
            phash=s.phash,
            width=s.width,
            height=s.height,
            size_bytes=s.size_bytes,
            author_id=user.id,
        )
        for s in stored
    ]
    session.add_all(photos)
    session.add(
        OrderEvent(
            order_id=order.id,
            actor_id=user.id,
            action="photo_added",
            data={"kind": kind.value, "count": len(photos)},
            created_at=now,
        )
    )
    order.updated_at = now
    _order_updated(session, order, "photos")
    await session.flush()
    return photos


async def delete_photo(session: AsyncSession, order: Order, photo_id: int, user: Employee) -> None:
    photo = await session.get(Photo, photo_id)
    if photo is None or photo.order_id != order.id:
        raise NotFound("Фото не найдено.")
    if photo.author_id != user.id and user.role not in (Role.MASTER, Role.ADMIN):
        raise Forbidden("Удалить фото может только тот, кто его сделал.")
    if order.status not in PRE_DONE_STATUSES | {S.REWORK}:
        raise Conflict("После «Исполнено» фото не удаляют — они нужны для проверки.")
    paths = (photo.path, photo.thumb_path)
    await session.delete(photo)
    _order_updated(session, order, "photos")
    await session.flush()
    delete_files(*paths)
