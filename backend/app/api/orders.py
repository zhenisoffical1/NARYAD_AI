from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, require_role
from app.errors import Invalid, NotFound
from app.models import Employee
from app.models.enums import OrderStatus, PhotoKind, Priority, Role
from app.schemas.orders import (
    ActionRequest,
    CompleteRequest,
    OrderCreate,
    OrderDetail,
    OrderListItem,
    OverrideRequest,
    PhotoOut,
    PriorityRequest,
    ReassignRequest,
)
from app.services import orders as svc
from app.services.notifications.live import commit_and_publish
from app.services.state_machine import Action

router = APIRouter(prefix="/orders", tags=["Наряды"])

master_only = require_role(Role.MASTER, Role.ADMIN)


@router.get("", response_model=list[OrderListItem], summary="Список нарядов с фильтрами")
async def list_orders(
    status: list[OrderStatus] = Query(default=[]),
    priority: list[Priority] = Query(default=[]),
    active: bool | None = None,
    overdue: bool | None = None,
    section_id: int | None = None,
    equipment_id: int | None = None,
    assignee_id: int | None = None,
    brigade_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    q: str | None = None,
    sort: str = Query(default="recent", pattern="^(recent|urgency)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrderListItem]:
    filters = svc.OrderFilters(
        statuses=status,
        priorities=priority,
        active=active,
        overdue=overdue,
        section_id=section_id,
        equipment_id=equipment_id,
        assignee_id=assignee_id,
        brigade_id=brigade_id,
        created_from=created_from,
        created_to=created_to,
        q=q,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return await svc.list_orders(session, user, filters)


@router.post("", response_model=OrderDetail, status_code=201, summary="Выдать наряд")
async def create_order(
    body: OrderCreate,
    user: Employee = Depends(master_only),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    order = await svc.create_order(session, body, user)
    await commit_and_publish(session)
    return await svc.order_detail(session, order.id, user)


@router.get("/{order_id}", response_model=OrderDetail, summary="Карточка наряда")
async def get_order(
    order_id: int,
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    return await svc.order_detail(session, order_id, user)


@router.post(
    "/{order_id}/actions/{action}",
    response_model=OrderDetail,
    summary="Действие по наряду: принять, в очередь, отклонить, начать, приостановить…",
)
async def order_action(
    order_id: int,
    action: str,
    body: ActionRequest | None = None,
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    try:
        parsed = Action(action)
    except ValueError as exc:
        raise NotFound(f"Действия «{action}» нет.") from exc
    order = await svc.load_order(session, order_id)
    await svc.perform_action(session, order, parsed, user, body or ActionRequest())
    await commit_and_publish(session)
    return await svc.order_detail(session, order_id, user)


@router.post(
    "/{order_id}/complete", response_model=OrderDetail, summary="Исполнено: форма закрытия"
)
async def complete_order(
    order_id: int,
    body: CompleteRequest,
    user: Employee = Depends(require_role(Role.WORKER)),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    order = await svc.load_order(session, order_id)
    await svc.complete_order(session, order, user, body)
    await commit_and_publish(session)
    return await svc.order_detail(session, order_id, user)


@router.post(
    "/{order_id}/reassign", response_model=OrderDetail, summary="Переназначить исполнителя"
)
async def reassign_order(
    order_id: int,
    body: ReassignRequest,
    user: Employee = Depends(master_only),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    order = await svc.load_order(session, order_id)
    await svc.reassign_order(session, order, user, body)
    await commit_and_publish(session)
    return await svc.order_detail(session, order_id, user)


@router.post("/{order_id}/priority", response_model=OrderDetail, summary="Сменить приоритет")
async def change_priority(
    order_id: int,
    body: PriorityRequest,
    user: Employee = Depends(master_only),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    order = await svc.load_order(session, order_id)
    await svc.change_priority(session, order, user, body)
    await commit_and_publish(session)
    return await svc.order_detail(session, order_id, user)


@router.post(
    "/{order_id}/assessment/override",
    response_model=OrderDetail,
    summary="Изменить оценку ИИ (решение мастера)",
)
async def override_assessment(
    order_id: int,
    body: OverrideRequest,
    user: Employee = Depends(master_only),
    session: AsyncSession = Depends(get_session),
) -> OrderDetail:
    order = await svc.load_order(session, order_id)
    await svc.override_assessment(session, order, user, body)
    await commit_and_publish(session)
    return await svc.order_detail(session, order_id, user)


@router.post(
    "/{order_id}/photos",
    response_model=list[PhotoOut],
    status_code=201,
    summary="Приложить фото (до 5 на «до» и «после»)",
)
async def upload_photos(
    order_id: int,
    kind: PhotoKind = Query(),
    files: list[UploadFile] = File(),
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PhotoOut]:
    order = await svc.load_order(session, order_id)
    svc.ensure_can_view(order, user)
    if len(files) > 5:
        raise Invalid("За один раз можно загрузить не больше 5 фото.")
    payloads = [await f.read() for f in files]
    photos = await svc.add_photos(session, order, user, kind, payloads)
    await commit_and_publish(session)
    return [svc.photo_out(p) for p in photos]


@router.delete("/{order_id}/photos/{photo_id}", status_code=204, summary="Удалить фото")
async def delete_photo(
    order_id: int,
    photo_id: int,
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    order = await svc.load_order(session, order_id)
    svc.ensure_can_view(order, user)
    await svc.delete_photo(session, order, photo_id, user)
    await commit_and_publish(session)
