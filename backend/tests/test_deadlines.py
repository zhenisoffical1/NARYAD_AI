"""Контроль сроков (ТЗ 6.1): время подменяется параметром `now`."""

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Employee, Notification, Order, OrderEvent
from app.models.enums import OrderStatus, Priority, Role
from app.services.deadlines import check_deadlines, duration
from tests.conftest import EmployeeFactory

S = OrderStatus
OrderFactory = Callable[..., Coroutine[Any, Any, Order]]


async def _notes(session: AsyncSession, kind: str) -> list[Notification]:
    return list(
        await session.scalars(
            select(Notification).where(Notification.kind == kind).order_by(Notification.id)
        )
    )


async def _check(session: AsyncSession, now: datetime) -> list[str]:
    fired = await check_deadlines(session, now=now)
    await session.commit()
    return [f.rule for f in fired]


def test_duration_format() -> None:
    assert duration(45) == "45 мин"
    assert duration(120) == "2 ч"
    assert duration(135) == "2 ч 15 мин"


async def test_overdue_message_matches_spec_example(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee(full_name="Ахметов Ерлан Каиртаевич")
    order = await order_factory(master=master, assignee=worker, status=S.IN_PROGRESS)
    started = datetime(2026, 10, 5, 9, 20, tzinfo=settings.tz)
    order.number = 147
    order.started_at = started
    order.deadline_at = started + timedelta(hours=1)
    session.add(
        OrderEvent(
            order_id=order.id,
            actor_id=worker.id,
            action="comment",
            comment="ждём подшипник со склада",
            created_at=started + timedelta(minutes=30),
        )
    )
    await session.commit()

    assert await _check(session, order.deadline_at + timedelta(minutes=45)) == ["overdue"]

    notes = await _notes(session, "order_overdue")
    assert {n.employee_id for n in notes} == {worker.id, master.id}
    assert notes[0].body == (
        "Наряд №147 просрочен на 45 мин. Дробилка КМД-1750, участок дробления. "
        "Исполнитель: Ахметов Е. Статус: в работе с 09:20. "
        "Последний комментарий: “ждём подшипник со склада”."
    )


async def test_overdue_repeats_after_interval_only(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker, status=S.QUEUED)
    now = order.deadline_at + timedelta(minutes=1)

    assert await _check(session, now) == ["overdue"]
    assert await _check(session, now + timedelta(minutes=settings.repeat_min - 1)) == []
    assert await _check(session, now + timedelta(minutes=settings.repeat_min)) == ["overdue"]
    assert len(await _notes(session, "order_overdue")) == 4  # дважды исполнителю и мастеру


async def test_reminder_before_deadline_once(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker, status=S.ACCEPTED)
    before = settings.remind_before_min

    assert await _check(session, order.deadline_at - timedelta(minutes=before + 5)) == []
    assert await _check(session, order.deadline_at - timedelta(minutes=before - 5)) == ["reminder"]
    assert await _check(session, order.deadline_at - timedelta(minutes=5)) == []
    (note,) = await _notes(session, "deadline_soon")
    assert note.employee_id == worker.id
    assert note.title.endswith("до срока 25 мин")


async def test_unaccepted_order_escalates_with_free_colleague(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee(specialty="слесарь-ремонтник")
    await make_employee(specialty="электромонтёр")
    colleague = await make_employee(
        full_name="Ковальчук Сергей Иванович", specialty="слесарь-ремонтник"
    )
    order = await order_factory(master=master, assignee=worker)
    issued = order.issued_at
    assert issued is not None

    limit = settings.unaccepted_min
    assert await _check(session, issued + timedelta(minutes=limit - 1)) == []
    assert await _check(session, issued + timedelta(minutes=limit)) == ["escalation"]

    (note,) = await _notes(session, "order_escalation")
    assert note.employee_id == master.id
    assert note.data == {"reassign_to": colleague.id, "reassign_name": "Ковальчук С."}
    assert "Свободен: Ковальчук С. (слесарь-ремонтник)" in note.body


async def test_emergency_escalates_after_three_minutes_and_rings_every_minute(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker)
    order.priority = Priority.EMERGENCY
    await session.commit()
    issued = order.issued_at
    assert issued is not None

    assert await _check(session, issued + timedelta(seconds=30)) == []
    assert await _check(session, issued + timedelta(minutes=1)) == ["alarm"]
    assert await _check(session, issued + timedelta(minutes=1, seconds=30)) == []
    assert await _check(session, issued + timedelta(minutes=3)) == ["alarm", "escalation"]

    alarms = await _notes(session, "order_alarm")
    assert len(alarms) == 2
    assert all(n.urgent and not n.feed and n.employee_id == worker.id for n in alarms)

    # Принял — звонки прекращаются
    order.status = S.ACCEPTED
    await session.commit()
    assert await _check(session, issued + timedelta(minutes=5)) == []


async def test_long_overdue_goes_to_boss_once(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    boss = await make_employee(Role.BOSS)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker, status=S.IN_PROGRESS)
    late = order.deadline_at + timedelta(minutes=settings.boss_overdue_min)

    assert "boss" in await _check(session, late)
    assert "boss" not in await _check(session, late + timedelta(hours=1))
    (note,) = await _notes(session, "order_overdue_boss")
    assert note.employee_id == boss.id
    assert "просрочен на 2 ч" in note.body


async def test_closed_orders_are_ignored(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker, status=S.AI_REVIEW)
    assert await _check(session, order.deadline_at + timedelta(hours=5)) == []


async def test_feed_hides_telegram_only_alarms(
    client: Any, session: AsyncSession, make_employee: EmployeeFactory
) -> None:
    from app.services.notifications.notify import notify
    from tests.conftest import auth_header

    worker: Employee = await make_employee()
    await notify(session, employee_id=worker.id, kind="order_new", title="a", body="b")
    await notify(
        session, employee_id=worker.id, kind="order_alarm", title="c", body="d", feed=False
    )
    await session.commit()

    resp = await client.get("/api/notifications", headers=auth_header(worker))
    assert resp.status_code == 200
    body = resp.json()
    assert [n["kind"] for n in body["items"]] == ["order_new"]
    assert body["unread"] == 1
