from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Employee, Notification, Order, OrderEvent
from app.models.base import utcnow
from app.models.enums import Role
from tests.conftest import auth_header
from tests.factories import Refs, jpeg_bytes, make_refs


@pytest.fixture(autouse=True)
def _media(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "media_dir", tmp_path)


@pytest.fixture
async def refs(session: AsyncSession) -> Refs:
    return await make_refs(session)


@pytest.fixture
async def team(make_employee, refs: Refs) -> dict[str, Employee]:
    return {
        "master": await make_employee(Role.MASTER, full_name="Ковалёв Андрей Петрович"),
        "worker": await make_employee(
            Role.WORKER,
            full_name="Ахметов Ерлан Каиртаевич",
            specialty="слесарь-ремонтник",
            brigade_id=refs.brigade.id,
        ),
        "other": await make_employee(
            Role.WORKER, full_name="Иванов Пётр Сергеевич", brigade_id=refs.brigade.id
        ),
        "boss": await make_employee(Role.BOSS),
        "admin": await make_employee(Role.ADMIN),
    }


async def issue(
    client: AsyncClient, master: Employee, refs: Refs, assignee: Employee, **extra: Any
) -> dict[str, Any]:
    body = {
        "description": "Течь масла из-под торцевого уплотнения",
        "equipment_id": refs.pump.id,
        "priority": "emergency",
        "assignee_id": assignee.id,
        **extra,
    }
    resp = await client.post("/api/orders", json=body, headers=auth_header(master))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def act(client: AsyncClient, user: Employee, order_id: int, action: str, **body: Any) -> Any:
    return await client.post(
        f"/api/orders/{order_id}/actions/{action}", json=body or None, headers=auth_header(user)
    )


async def upload(
    client: AsyncClient, user: Employee, order_id: int, kind: str, *payloads: bytes
) -> Any:
    files = [("files", (f"p{i}.jpg", data, "image/jpeg")) for i, data in enumerate(payloads)]
    return await client.post(
        f"/api/orders/{order_id}/photos",
        params={"kind": kind},
        files=files,
        headers=auth_header(user),
    )


# --- выдача -------------------------------------------------------------------


async def test_master_issues_order_with_defaults(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])

    assert order["number"] == 1
    assert order["status"] == "ISSUED"
    assert order["type"] == "unplanned"  # из приоритета
    assert order["equipment_stopped"] is True  # аварийный — оборудование стоит
    assert order["section"]["name"] == "Обогащение"  # участок из оборудования
    assert order["assignee"]["short_name"] == "Ахметов Е."
    assert order["events"][0]["action"] == "create"
    # Срок не указан — берётся из приоритета (аварийный: 2 ч)
    deadline = datetime.fromisoformat(order["deadline_at"])
    expected = utcnow() + timedelta(hours=settings.deadline_hours_emergency)
    assert abs((deadline - expected).total_seconds()) < 60

    note = await session.scalar(select(Notification))
    assert note is not None
    assert note.employee_id == team["worker"].id
    assert note.title == "Новый наряд №1 — АВАРИЙНЫЙ"

    second = await issue(client, team["master"], refs, team["worker"], priority="planned")
    assert second["number"] == 2
    assert second["type"] == "planned"
    assert second["equipment_stopped"] is False


async def test_worker_cannot_issue(client: AsyncClient, team, refs: Refs) -> None:
    resp = await client.post(
        "/api/orders",
        json={
            "description": "x" * 10,
            "equipment_id": refs.pump.id,
            "priority": "normal",
            "assignee_id": team["worker"].id,
        },
        headers=auth_header(team["worker"]),
    )
    assert resp.status_code == 403


async def test_issue_requires_assignee_or_brigade(client: AsyncClient, team, refs: Refs) -> None:
    resp = await client.post(
        "/api/orders",
        json={"description": "Шум подшипника", "equipment_id": refs.pump.id, "priority": "high"},
        headers=auth_header(team["master"]),
    )
    assert resp.status_code == 422
    assert "Выберите исполнителя или бригаду" in resp.json()["detail"]


async def test_issue_rejects_past_deadline(client: AsyncClient, team, refs: Refs) -> None:
    resp = await client.post(
        "/api/orders",
        json={
            "description": "Шум подшипника",
            "equipment_id": refs.pump.id,
            "priority": "high",
            "assignee_id": team["worker"].id,
            "deadline_at": (utcnow() - timedelta(minutes=5)).isoformat(),
        },
        headers=auth_header(team["master"]),
    )
    assert resp.status_code == 422
    assert "Срок уже прошёл" in resp.json()["detail"]


# --- видимость ----------------------------------------------------------------


async def test_worker_sees_only_own_orders(client: AsyncClient, team, refs: Refs) -> None:
    mine = await issue(client, team["master"], refs, team["worker"])
    theirs = await issue(client, team["master"], refs, team["other"])

    resp = await client.get("/api/orders", headers=auth_header(team["worker"]))
    assert [o["id"] for o in resp.json()] == [mine["id"]]

    forbidden = await client.get(f"/api/orders/{theirs['id']}", headers=auth_header(team["worker"]))
    assert forbidden.status_code == 403

    staff = await client.get("/api/orders", headers=auth_header(team["boss"]))
    assert len(staff.json()) == 2


async def test_brigade_order_taken_by_member(client: AsyncClient, team, refs: Refs) -> None:
    resp = await client.post(
        "/api/orders",
        json={
            "description": "Плановая замена фильтров",
            "equipment_id": refs.crusher.id,
            "priority": "planned",
            "brigade_id": refs.brigade.id,
        },
        headers=auth_header(team["master"]),
    )
    order = resp.json()
    assert order["assignee"] is None

    visible = await client.get("/api/orders", headers=auth_header(team["other"]))
    assert [o["id"] for o in visible.json()] == [order["id"]]

    taken = await act(client, team["other"], order["id"], "accept")
    assert taken.status_code == 200
    assert taken.json()["assignee"]["id"] == team["other"].id

    # Теперь он личный — второму члену бригады больше не виден
    after = await client.get("/api/orders", headers=auth_header(team["worker"]))
    assert after.json() == []


# --- действия и закрытие ------------------------------------------------------


async def test_full_cycle_through_api(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    master, worker = team["master"], team["worker"]
    order = await issue(client, master, refs, worker)
    oid = order["id"]
    assert set(order["actions"]) >= {"reassign", "change_priority", "cancel"}

    worker_view = await client.get(f"/api/orders/{oid}", headers=auth_header(worker))
    assert set(worker_view.json()["actions"]) == {"accept", "queue", "reject"}

    assert (await act(client, worker, oid, "accept")).status_code == 200
    started = await act(client, worker, oid, "start")
    assert started.json()["status"] == "IN_PROGRESS"
    assert "complete" in started.json()["actions"]

    paused = await act(client, worker, oid, "pause", reason="ждёт запчасти")
    assert paused.json()["status"] == "PAUSED"
    await act(client, worker, oid, "resume")

    # Внеплановый без фото «после» закрыть нельзя
    body = {
        "works_done": "Заменено торцевое уплотнение, подтянуты фланцы",
        "fault_code_id": refs.code_hydraulic.id,
        "materials": [{"material_id": refs.oil.id, "quantity": "1.5"}],
    }
    no_photo = await client.post(
        f"/api/orders/{oid}/complete", json=body, headers=auth_header(worker)
    )
    assert no_photo.status_code == 422
    assert "фото «после»" in no_photo.json()["detail"]

    photo = await upload(client, worker, oid, "after", jpeg_bytes(taken_at=utcnow()))
    assert photo.status_code == 201
    assert photo.json()[0]["thumb_url"].endswith("_thumb.jpg")

    done = await client.post(f"/api/orders/{oid}/complete", json=body, headers=auth_header(worker))
    assert done.status_code == 200, done.text
    detail = done.json()
    assert detail["status"] == "AI_REVIEW"  # «Исполнено» сразу уходит на проверку
    assert detail["materials"][0]["name"] == "Масло И-40А"
    assert detail["fault_code"]["code"] == "Г-02"
    assert detail["downtime_minutes"] is not None

    closed = await act(client, master, oid, "close", comment="Принято")
    assert closed.json()["status"] == "CLOSED"

    actions = [
        e.action
        for e in await session.scalars(
            select(OrderEvent).where(OrderEvent.order_id == oid).order_by(OrderEvent.id)
        )
    ]
    assert actions == [
        "create",
        "accept",
        "start",
        "pause",
        "resume",
        "photo_added",
        "complete",
        "begin_review",
        "ai_checked",
        "close",
    ]

    final = (await client.get(f"/api/orders/{oid}", headers=auth_header(master))).json()
    assert final["assessment"]["status"] == "done"
    assert final["assessment"]["verdict"] in ("accepted", "accepted_with_remarks")
    assert [c["key"] for c in final["assessment"]["checks"]] == [
        "completeness",
        "time",
        "materials",
        "works_match",
        "photos",
    ]


async def test_invalid_transition_returns_409_in_russian(
    client: AsyncClient, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    resp = await act(client, team["worker"], order["id"], "start")
    assert resp.status_code == 409
    assert "Нельзя «Начать»" in resp.json()["detail"]
    assert "«Принять в работу»" in resp.json()["detail"]


async def test_reject_requires_reason_and_notifies_master(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    no_reason = await act(client, team["worker"], order["id"], "reject")
    assert no_reason.status_code == 422

    ok = await act(client, team["worker"], order["id"], "reject", reason="нет допуска")
    assert ok.json()["status"] == "REJECTED"
    notes = (
        await session.scalars(
            select(Notification).where(Notification.employee_id == team["master"].id)
        )
    ).all()
    assert notes[-1].title == f"Наряд №{order['number']} отклонён"
    assert "нет допуска" in notes[-1].body


async def test_complete_requires_materials_or_flag(client: AsyncClient, team, refs: Refs) -> None:
    order = await issue(client, team["master"], refs, team["worker"], priority="planned")
    for action in ("accept", "start"):
        await act(client, team["worker"], order["id"], action)
    body = {"works_done": "Проведено ТО", "fault_code_id": refs.code_hydraulic.id}
    resp = await client.post(
        f"/api/orders/{order['id']}/complete", json=body, headers=auth_header(team["worker"])
    )
    assert resp.status_code == 422
    assert "«Без материалов»" in resp.json()["detail"]

    resp = await client.post(
        f"/api/orders/{order['id']}/complete",
        json={**body, "no_materials": True},
        headers=auth_header(team["worker"]),
    )
    assert resp.status_code == 200  # плановый — фото «после» не обязательно


# --- мастер -------------------------------------------------------------------


async def test_reassign_returns_order_to_issued(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    await act(client, team["worker"], order["id"], "accept")

    resp = await client.post(
        f"/api/orders/{order['id']}/reassign",
        json={"assignee_id": team["other"].id, "comment": "Ахметов ушёл на аварию"},
        headers=auth_header(team["master"]),
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "ISSUED"
    assert detail["assignee"]["id"] == team["other"].id
    assert detail["events"][-1]["action"] == "reassign"

    titles = [n.title for n in await session.scalars(select(Notification))]
    assert f"Вам передан наряд №{order['number']}" in titles
    assert f"Наряд №{order['number']} передан другому исполнителю" in titles


async def test_reissue_after_reject(client: AsyncClient, team, refs: Refs) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    await act(client, team["worker"], order["id"], "reject", reason="занят аварийным")
    resp = await client.post(
        f"/api/orders/{order['id']}/reassign",
        json={"assignee_id": team["other"].id},
        headers=auth_header(team["master"]),
    )
    assert resp.json()["status"] == "ISSUED"
    assert resp.json()["events"][-1]["action"] == "reissue"


async def test_change_priority_and_cancel(client: AsyncClient, team, refs: Refs) -> None:
    order = await issue(client, team["master"], refs, team["worker"], priority="normal")
    resp = await client.post(
        f"/api/orders/{order['id']}/priority",
        json={"priority": "high"},
        headers=auth_header(team["master"]),
    )
    assert resp.json()["priority"] == "high"
    assert resp.json()["events"][-1]["data"] == {"from": "normal", "to": "high"}

    cancelled = await act(client, team["master"], order["id"], "cancel", reason="ошибка выдачи")
    assert cancelled.json()["status"] == "CANCELLED"
    again = await act(client, team["master"], order["id"], "cancel", reason="ещё раз")
    assert again.status_code == 409


async def test_override_needs_assessment(client: AsyncClient, team, refs: Refs) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    resp = await client.post(
        f"/api/orders/{order['id']}/assessment/override",
        json={"score": 80, "comment": "Проверил на месте"},
        headers=auth_header(team["master"]),
    )
    assert resp.status_code == 409


# --- фото ---------------------------------------------------------------------


async def test_photo_exif_time_and_limit(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    shot = utcnow().replace(microsecond=0) - timedelta(minutes=3)
    resp = await upload(
        client, team["master"], order["id"], "before", *(jpeg_bytes(mark=i) for i in range(4))
    )
    assert resp.status_code == 201
    one = await upload(client, team["master"], order["id"], "before", jpeg_bytes(taken_at=shot))
    assert one.json()[0]["taken_at"].startswith(shot.strftime("%Y-%m-%dT%H:%M"))

    sixth = await upload(client, team["master"], order["id"], "before", jpeg_bytes())
    assert sixth.status_code == 422
    assert "не больше 5 фото «до»" in sixth.json()["detail"]


async def test_photo_rejects_non_image(client: AsyncClient, team, refs: Refs) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    resp = await upload(client, team["master"], order["id"], "before", b"not an image")
    assert resp.status_code == 422
    assert "не похож на фотографию" in resp.json()["detail"]


async def test_after_photo_only_by_assignee_in_progress(
    client: AsyncClient, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    early = await upload(client, team["worker"], order["id"], "after", jpeg_bytes())
    assert early.status_code == 409  # ещё не начат

    by_master = await upload(client, team["master"], order["id"], "after", jpeg_bytes())
    assert by_master.status_code == 403


# --- люди и смена -------------------------------------------------------------


async def test_people_statuses(
    client: AsyncClient, session: AsyncSession, make_employee, team, refs: Refs
) -> None:
    off = await make_employee(Role.WORKER, full_name="Сидоров Олег Ильич", on_shift=False)
    busy = await issue(client, team["master"], refs, team["worker"])
    await act(client, team["worker"], busy["id"], "accept")
    await act(client, team["worker"], busy["id"], "start")
    await issue(client, team["master"], refs, team["other"])
    await issue(client, team["master"], refs, team["other"])

    resp = await client.get("/api/people/shift", headers=auth_header(team["master"]))
    by_id = {p["employee"]["id"]: p for p in resp.json()}
    assert by_id[team["worker"].id]["state"] == "busy"
    assert by_id[team["worker"].id]["current_order"]["number"] == busy["number"]
    assert by_id[team["other"].id]["state"] == "queue"
    assert by_id[team["other"].id]["queue_count"] == 2
    assert by_id[off.id]["state"] == "off_shift"

    denied = await client.get("/api/people/shift", headers=auth_header(team["worker"]))
    assert denied.status_code == 403


async def test_shift_summary_counts(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    order = await issue(client, team["master"], refs, team["worker"])
    db_order = await session.get(Order, order["id"])
    assert db_order is not None
    db_order.deadline_at = utcnow() - timedelta(minutes=10)
    await session.commit()

    resp = await client.get("/api/shift/summary", headers=auth_header(team["master"]))
    summary = resp.json()
    assert summary["issued"] == 1
    assert summary["overdue"] == 1
    assert summary["equipment_down"] == 1

    listed = await client.get(
        "/api/orders", params={"overdue": True}, headers=auth_header(team["master"])
    )
    assert listed.json()[0]["is_overdue"] is True
    assert listed.json()[0]["overdue_minutes"] >= 9


async def test_equipment_history_and_recent(client: AsyncClient, team, refs: Refs) -> None:
    await issue(client, team["master"], refs, team["worker"])
    await issue(client, team["master"], refs, team["worker"], equipment_id=refs.crusher.id)

    history = await client.get(
        f"/api/equipment/{refs.pump.id}/history", headers=auth_header(team["boss"])
    )
    assert history.json()["orders_total"] == 1
    assert history.json()["unplanned_total"] == 1

    recent = await client.get("/api/equipment/recent", headers=auth_header(team["master"]))
    assert [e["inv_number"] for e in recent.json()] == ["ДР-001", "ОБ-007"]

    qr = await client.get("/api/equipment/by-qr/QR-OB-007", headers=auth_header(team["master"]))
    assert qr.json()["id"] == refs.pump.id


async def test_fault_codes_include_norms(client: AsyncClient, team, refs: Refs) -> None:
    resp = await client.get("/api/fault-codes", headers=auth_header(team["worker"]))
    code = resp.json()[0]
    assert code["norm_hours"] == "1.50"
    assert code["norm_materials"][0]["name"] == "Масло И-40А"


# --- администрирование --------------------------------------------------------


async def test_admin_crud_and_csv_import(client: AsyncClient, team, refs: Refs) -> None:
    admin = auth_header(team["admin"])
    created = await client.post("/api/admin/sections", json={"name": "Дробление"}, headers=admin)
    assert created.status_code == 201

    dup = await client.post("/api/admin/sections", json={"name": "Дробление"}, headers=admin)
    assert dup.status_code == 409

    csv_text = (
        "name;inv_number;section;type;criticality\n"
        "Конвейер К-3;КТ-003;Дробление;Конвейер;A\n"
        "Насос гидравлический Н-7;ОБ-007;Обогащение;Насос;B\n"
    )
    resp = await client.post(
        "/api/admin/equipment/import",
        files={"file": ("eq.csv", csv_text.encode("utf-8"), "text/csv")},
        headers=admin,
    )
    assert resp.json() == {"created": 1, "updated": 1, "errors": []}

    bad = await client.post(
        "/api/admin/equipment/import",
        files={"file": ("eq.csv", "name;inv_number;section;type\nX;Y-1;Нет такого;Т\n".encode())},
        headers=admin,
    )
    assert bad.json()["errors"] == ["Строка 2: участок «Нет такого» не найден"]

    emp = await client.post(
        "/api/admin/employees",
        json={"login": "novikov", "full_name": "Новиков Илья", "role": "worker", "pin": "5555"},
        headers=admin,
    )
    assert emp.status_code == 201
    login = await client.post("/api/auth/login", json={"login": "novikov", "pin": "5555"})
    assert login.status_code == 200

    not_admin = await client.get("/api/admin/sections", headers=auth_header(team["master"]))
    assert not_admin.status_code == 403


async def test_status_change_ordering_in_list(client: AsyncClient, team, refs: Refs) -> None:
    await issue(client, team["master"], refs, team["worker"], priority="planned")
    await issue(client, team["master"], refs, team["worker"], priority="emergency")
    resp = await client.get(
        "/api/orders",
        params={"sort": "urgency", "active": True},
        headers=auth_header(team["worker"]),
    )
    assert [o["priority"] for o in resp.json()] == ["emergency", "planned"]


async def test_live_event_reaches_assignee(client: AsyncClient, team, refs: Refs) -> None:
    from starlette.testclient import TestClient

    from app.main import app
    from app.security import create_access_token

    token = create_access_token(team["worker"].id, Role.WORKER)
    with TestClient(app) as tc, tc.websocket_connect(f"/ws?token={token}") as ws:
        ws.receive_json()
        resp = tc.post(
            "/api/orders",
            json={
                "description": "Течь масла",
                "equipment_id": refs.pump.id,
                "priority": "emergency",
                "assignee_id": team["worker"].id,
            },
            headers=auth_header(team["master"]),
        )
        assert resp.status_code == 201
        types = {ws.receive_json()["type"], ws.receive_json()["type"]}
        assert types == {"order.created", "notification.created"}
