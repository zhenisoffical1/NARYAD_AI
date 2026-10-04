"""Рейтинг, подсказки при выдаче и лента уведомлений — на полной тестовой базе из сида."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Equipment
from app.models.base import utcnow
from seed.demo import build_scene, set_history_end
from seed.history import generate_history
from seed.world import build_world
from tests.conftest import auth_header


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[str, Employee]:
    now = utcnow()
    world = await build_world(session)
    history = await generate_history(session, world, now)
    await set_history_end(session, history.history_end)
    await build_scene(session, now)
    await session.commit()
    return {e.login: e for e in await session.scalars(select(Employee))}


async def _equipment(session: AsyncSession, inv: str) -> int:
    equipment = await session.scalar(select(Equipment).where(Equipment.inv_number == inv))
    assert equipment is not None
    return equipment.id


async def test_rating_formula_and_explanation(client: AsyncClient, seeded) -> None:
    resp = await client.get("/api/rating", params={"days": 90}, headers=auth_header(seeded["boss"]))
    assert resp.status_code == 200
    report = resp.json()
    rated = [w for w in report["workers"] if w["score"] is not None]
    assert len(rated) >= 12
    top = rated[0]
    assert [c["key"] for c in top["components"]] == [
        "quality",
        "on_time",
        "no_returns",
        "volume",
        "no_rejects",
    ]
    # Баллы составляющих складываются в рейтинг
    assert abs(sum(c["points"] for c in top["components"]) - top["score"]) < 0.5
    assert top["explanation"].startswith(f"Рейтинг {round(top['score'])} из 100 за 90 дн.")
    assert "Больше всего поднимет" in top["explanation"] or "так держать" in top["explanation"]
    assert len(report["brigades"]) == 3


async def test_returns_pattern_shows_in_rating(client: AsyncClient, seeded) -> None:
    """Исполнитель с частыми возвратами проседает именно по этой составляющей."""
    resp = await client.get("/api/rating", params={"days": 90}, headers=auth_header(seeded["boss"]))
    workers = {w["employee"]["id"]: w for w in resp.json()["workers"]}
    melnikov = workers[seeded["melnikov"].id]
    others = [
        c["value"]
        for wid, w in workers.items()
        if wid != seeded["melnikov"].id and w["score"] is not None
        for c in w["components"]
        if c["key"] == "no_returns"
    ]
    mine = next(c["value"] for c in melnikov["components"] if c["key"] == "no_returns")
    assert mine < min(others)


async def test_my_rating_for_worker(client: AsyncClient, seeded) -> None:
    resp = await client.get("/api/rating/me", headers=auth_header(seeded["akhmetov"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["employee"]["short_name"] == "Ахметов Е."
    assert body["total_rated"] >= 1

    denied = await client.get("/api/rating", headers=auth_header(seeded["akhmetov"]))
    assert denied.status_code == 403


async def test_assist_recommends_free_electrician_for_motor(
    client: AsyncClient, session: AsyncSession, seeded
) -> None:
    resp = await client.post(
        "/api/orders/assist",
        json={
            "equipment_id": await _equipment(session, "КТ-004"),
            "description": "Двигатель привода греется, срабатывает тепловая защита",
            "priority": "high",
        },
        headers=auth_header(seeded["master1"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["specialty"] == "электромонтёр"
    first = body["candidates"][0]
    assert first["recommended"] is True
    assert first["specialty"] == "электромонтёр"
    assert first["person"]["state"] == "free"
    assert first["reason"].startswith("электромонтёр")
    assert body["fault_code"]["code"].startswith("Э")


async def test_assist_for_pump_leak(client: AsyncClient, session: AsyncSession, seeded) -> None:
    resp = await client.post(
        "/api/orders/assist",
        json={
            "equipment_id": await _equipment(session, "ОБ-007"),
            "description": "Течь масла на насосе, лужа под уплотнением",
            "priority": "emergency",
        },
        headers=auth_header(seeded["master1"]),
    )
    body = resp.json()
    first = body["candidates"][0]
    assert first["specialty"] == "слесарь-ремонтник"
    assert first["person"]["employee"]["full_name"].split()[0] in ("Ахметов", "Ковальчук")
    assert body["fault_code"]["code"] == "Г-02"
    assert body["deadline_hours"] == 2  # аварийный: 2 ч, норматив Г-02 меньше
    # Не на смене — всегда в конце списка
    states = [c["person"]["state"] for c in body["candidates"]]
    assert states.index("off_shift") > max(i for i, s in enumerate(states) if s != "off_shift") - 1


async def test_notifications_feed_and_read(
    client: AsyncClient, session: AsyncSession, seeded
) -> None:
    worker = seeded["kovalchuk"]
    await client.post(
        "/api/orders",
        json={
            "description": "Шум подшипника приводного барабана",
            "equipment_id": await _equipment(session, "КТ-003"),
            "priority": "high",
            "assignee_id": worker.id,
        },
        headers=auth_header(seeded["master1"]),
    )
    feed = (await client.get("/api/notifications", headers=auth_header(worker))).json()
    assert feed["unread"] == 1
    assert feed["items"][0]["title"].startswith("Новый наряд №")

    await client.post("/api/notifications/read", json={}, headers=auth_header(worker))
    feed = (await client.get("/api/notifications", headers=auth_header(worker))).json()
    assert feed["unread"] == 0
