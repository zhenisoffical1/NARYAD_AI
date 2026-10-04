"""Telegram: привязка по deep link, кнопки в сообщениях, действия через state_machine."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers import handle_callback, link_chat, unlink_chat
from app.bot.messages import callback_action, callback_reassign, render
from app.errors import Conflict, Forbidden
from app.models import Notification, Order
from app.models.base import utcnow
from app.models.enums import OrderStatus, Role
from app.services.state_machine import Action
from app.services.telegram_link import make_token, parse_token
from tests.conftest import EmployeeFactory, auth_header

S = OrderStatus
OrderFactory = Callable[..., Coroutine[Any, Any, Order]]


def test_link_token_round_trip_and_tampering() -> None:
    now = utcnow()
    token, expires_at = make_token(42, now)
    assert len(token) <= 64 and all(c.isalnum() or c in "-_" for c in token)
    assert parse_token(token, now) == 42
    assert parse_token(token, expires_at + timedelta(seconds=1)) is None
    assert parse_token(token.replace("42-", "43-", 1), now) is None
    assert parse_token("мусор", now) is None


async def test_link_moves_chat_to_new_owner(
    session: AsyncSession, make_employee: EmployeeFactory
) -> None:
    old = await make_employee()
    new = await make_employee(full_name="Ахметов Ерлан Каиртаевич")
    old.telegram_chat_id = 555
    await session.commit()

    token, _ = make_token(new.id, utcnow())
    reply = await link_chat(session, token, 555)
    assert reply.startswith("Готово, Ахметов Ерлан Каиртаевич")
    await session.refresh(old)
    await session.refresh(new)
    assert old.telegram_chat_id is None and new.telegram_chat_id == 555

    assert "отключены" in await unlink_chat(session, 555)
    assert "устарела" in await link_chat(session, "1-1-bad", 555)


async def test_expired_link_is_refused(
    session: AsyncSession, make_employee: EmployeeFactory
) -> None:
    worker = await make_employee()
    token, _ = make_token(worker.id, utcnow() - timedelta(hours=1))
    assert "устарела" in await link_chat(session, token, 777)


async def test_new_order_message_has_accept_and_queue_buttons(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    order = await order_factory(master=master, assignee=worker)
    note = Notification(
        employee_id=worker.id, order_id=order.id, kind="order_new", title="Новый <наряд>", body="x"
    )
    out = render(note, worker)
    assert out.text.startswith("<b>Новый &lt;наряд&gt;</b>")
    assert [(b.text, b.callback) for b in out.rows[0]] == [
        ("Принять в работу", callback_action(order.id, Action.ACCEPT)),
        ("Поставить в очередь", callback_action(order.id, Action.QUEUE)),
    ]


async def test_accept_from_telegram_goes_through_state_machine(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    worker.telegram_chat_id = 1001
    order = await order_factory(master=master, assignee=worker)
    await session.commit()

    result = await handle_callback(session, 1001, callback_action(order.id, Action.ACCEPT))
    assert result.startswith("Принят в работу")
    await session.refresh(order)
    assert order.status == S.ACCEPTED

    # Повторное нажатие — понятная ошибка, а не падение
    with pytest.raises(Conflict):
        await handle_callback(session, 1001, callback_action(order.id, Action.ACCEPT))


async def test_unlinked_chat_and_foreign_order_are_refused(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee()
    other = await make_employee()
    other.telegram_chat_id = 2002
    order = await order_factory(master=master, assignee=worker)
    await session.commit()

    with pytest.raises(Forbidden):
        await handle_callback(session, 9999, callback_action(order.id, Action.ACCEPT))
    with pytest.raises(Forbidden):
        await handle_callback(session, 2002, callback_action(order.id, Action.ACCEPT))


async def test_master_reassigns_from_escalation_button(
    session: AsyncSession, make_employee: EmployeeFactory, order_factory: OrderFactory
) -> None:
    master = await make_employee(Role.MASTER)
    master.telegram_chat_id = 3003
    worker = await make_employee()
    colleague = await make_employee(full_name="Ковальчук Сергей Иванович")
    order = await order_factory(master=master, assignee=worker)
    await session.commit()

    note = Notification(
        employee_id=master.id,
        order_id=order.id,
        kind="order_escalation",
        title="t",
        body="b",
        data={"reassign_to": colleague.id, "reassign_name": "Ковальчук С."},
    )
    (button,) = render(note, master).rows[0]
    assert button.text == "Переназначить: Ковальчук С."
    assert button.callback == callback_reassign(order.id, colleague.id)

    result = await handle_callback(session, 3003, button.callback)
    assert result.startswith("Выдан — Ковальчук С.")
    await session.refresh(order)
    assert order.assignee_id == colleague.id


async def test_telegram_api_without_bot(
    client: AsyncClient, make_employee: EmployeeFactory
) -> None:
    worker = await make_employee()
    resp = await client.get("/api/telegram", headers=auth_header(worker))
    assert resp.json() == {"available": False, "linked": False, "bot_username": None}
    resp = await client.post("/api/telegram/link", headers=auth_header(worker))
    assert resp.status_code == 409
