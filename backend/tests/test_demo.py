"""Пульт демо: сброс сцены, «промотать до просрочки», вход по QR. Только при DEMO_MODE."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification
from app.services.deadlines import check_deadlines
from tests.test_seed import _seed


@pytest.fixture
def demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)


async def test_demo_api_is_hidden_without_demo_mode(client: AsyncClient) -> None:
    assert (await client.get("/api/demo")).status_code == 404
    assert (await client.post("/api/demo/login", json={"login": "master1"})).status_code == 404


@pytest.mark.usefixtures("demo_mode")
async def test_demo_console_flow(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session)

    # Свежая сцена не «звонит» сама по себе: ни просрочек, ни напоминаний
    assert await check_deadlines(session) == []
    await session.rollback()

    state = (await client.get("/api/demo")).json()
    logins = {a["login"]: a for a in state["accounts"]}
    assert logins["akhmetov"]["state"] == "free"
    assert logins["baizhanov"]["state"] == "queue"
    queued = next(o for o in state["orders"] if o["status"] == "QUEUED")

    # Шаг 4 сценария ТЗ: наряд в очереди просрочен — сообщение исполнителю и мастеру
    resp = await client.post(f"/api/demo/orders/{queued['id']}/overdue")
    assert resp.status_code == 200, resp.text
    assert resp.json()["rules"] == ["overdue"]
    notes = list(
        await session.scalars(
            select(Notification).where(
                Notification.order_id == queued["id"], Notification.kind == "order_overdue"
            )
        )
    )
    assert {n.employee_id for n in notes} == {logins["baizhanov"]["id"], logins["master1"]["id"]}
    assert notes[0].body.startswith(f"Наряд №{queued['number']} просрочен на 5 мин.")

    # Принятый наряд эскалировать нельзя — понятная ошибка
    accepted = next(o for o in state["orders"] if o["status"] == "ACCEPTED")
    resp = await client.post(f"/api/demo/orders/{accepted['id']}/unaccepted")
    assert resp.status_code == 409

    # Вход с телефона по QR
    resp = await client.post("/api/demo/login", json={"login": "akhmetov"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "worker"

    # Сброс возвращает сцену в исходное состояние
    assert (await client.post("/api/demo/reset")).status_code == 200
    again = (await client.get("/api/demo")).json()
    assert len(again["orders"]) == len(state["orders"])
    assert not any(o["overdue"] for o in again["orders"])
