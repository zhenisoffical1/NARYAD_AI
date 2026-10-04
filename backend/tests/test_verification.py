"""ИИ-проверка закрытого наряда: правила, фото, итог и автоматический возврат на доработку."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Employee, Notification, Order
from app.models.base import utcnow
from app.models.enums import OrderType, Priority, Role, Verdict
from app.services.verification.aggregate import aggregate
from app.services.verification.facts import CheckResult, ClosureFacts, MaterialFact
from app.services.verification.llm_check import mock_works_match
from app.services.verification.rules import check_materials, check_time, run_rules
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
        "worker": await make_employee(Role.WORKER, full_name="Ахметов Ерлан Каиртаевич"),
    }


async def _in_progress(
    client: AsyncClient, team: dict[str, Employee], refs: Refs, **extra: Any
) -> int:
    resp = await client.post(
        "/api/orders",
        json={
            "description": "Течь масла из-под торцевого уплотнения насоса",
            "equipment_id": refs.pump.id,
            "priority": "high",
            "assignee_id": team["worker"].id,
            **extra,
        },
        headers=auth_header(team["master"]),
    )
    oid = resp.json()["id"]
    for action in ("accept", "start"):
        await client.post(
            f"/api/orders/{oid}/actions/{action}", headers=auth_header(team["worker"])
        )
    # Работа шла 80 минут — иначе проверка справедливо скажет «подозрительно быстро»
    async with SessionLocal() as session:
        order = await session.get(Order, oid)
        assert order is not None and order.started_at is not None
        order.started_at -= timedelta(minutes=80)
        order.issued_at = order.created_at = order.started_at - timedelta(minutes=5)
        await session.commit()
    return int(oid)


async def _photo(client: AsyncClient, user: Employee, oid: int, kind: str, data: bytes) -> None:
    resp = await client.post(
        f"/api/orders/{oid}/photos",
        params={"kind": kind},
        files=[("files", ("p.jpg", data, "image/jpeg"))],
        headers=auth_header(user),
    )
    assert resp.status_code == 201, resp.text


async def _complete(
    client: AsyncClient, worker: Employee, oid: int, refs: Refs, works: str, oil: str = "1.5"
) -> dict[str, Any]:
    resp = await client.post(
        f"/api/orders/{oid}/complete",
        json={
            "works_done": works,
            "fault_code_id": refs.code_hydraulic.id,
            "materials": [{"material_id": refs.oil.id, "quantity": oil}],
        },
        headers=auth_header(worker),
    )
    assert resp.status_code == 200, resp.text
    detail = await client.get(f"/api/orders/{oid}", headers=auth_header(worker))
    return dict(detail.json())


async def test_good_closure_waits_for_master(client: AsyncClient, team, refs: Refs) -> None:
    oid = await _in_progress(client, team, refs)
    await _photo(client, team["worker"], oid, "after", jpeg_bytes(taken_at=utcnow(), mark=1))
    detail = await _complete(
        client,
        team["worker"],
        oid,
        refs,
        "Заменено торцевое уплотнение, течь устранена, масло долито",
    )
    assert detail["status"] == "AI_REVIEW"  # финальное слово за мастером
    assessment = detail["assessment"]
    assert assessment["verdict"] == "accepted", " | ".join(
        f"{c['key']}:{c['status']}:{c['detail']}"
        for c in assessment["checks"]
        if c["status"] != "ok"
    )
    assert assessment["score_0_100"] == 100
    assert assessment["explanation_master"] is None  # исполнителю — только его отчёт
    assert "Наряд №" in assessment["explanation_worker"]


async def test_works_not_matching_problem_go_to_rework(
    client: AsyncClient, session: AsyncSession, team, refs: Refs
) -> None:
    oid = await _in_progress(client, team, refs)
    await _photo(client, team["worker"], oid, "after", jpeg_bytes(taken_at=utcnow(), mark=2))
    detail = await _complete(
        client, team["worker"], oid, refs, "Заменён контактор в шкафу управления, протянуты клеммы"
    )
    assert detail["status"] == "REWORK"
    assert detail["assessment"]["verdict"] == "rework"
    rework_event = detail["events"][-1]
    assert rework_event["action"] == "send_to_rework"
    assert rework_event["actor"] is None  # вернула система по вердикту ИИ
    assert rework_event["reason"].startswith("Вердикт ИИ:")

    titles = [n.title for n in await session.scalars(select(Notification))]
    assert any("нужна доработка" in t for t in titles)


async def test_material_overuse_is_named_with_numbers(
    client: AsyncClient, team, refs: Refs
) -> None:
    oid = await _in_progress(client, team, refs)
    await _photo(client, team["worker"], oid, "after", jpeg_bytes(taken_at=utcnow(), mark=3))
    detail = await _complete(
        client, team["worker"], oid, refs, "Заменено уплотнение, течь устранена", oil="6"
    )
    materials = next(c for c in detail["assessment"]["checks"] if c["key"] == "materials")
    assert materials["status"] == "fail"
    assert materials["detail"].startswith(
        "Списано 6 л «Масло И-40А» при норме 1,5 л для шифра Г-02"
    )
    assert detail["status"] == "REWORK"


async def test_duplicate_photo_from_other_order(client: AsyncClient, team, refs: Refs) -> None:
    same = jpeg_bytes(taken_at=utcnow(), mark=4)
    first = await _in_progress(client, team, refs)
    await _photo(client, team["worker"], first, "after", same)
    await _complete(client, team["worker"], first, refs, "Заменено уплотнение, течь устранена")

    second = await _in_progress(client, team, refs)
    await _photo(client, team["worker"], second, "after", same)
    detail = await _complete(
        client, team["worker"], second, refs, "Заменено уплотнение, течь устранена"
    )

    photos = next(c for c in detail["assessment"]["checks"] if c["key"] == "photos")
    assert photos["status"] == "fail"
    assert "совпадает со снимком из наряда №1" in photos["detail"]


async def test_after_photo_identical_to_before(client: AsyncClient, team, refs: Refs) -> None:
    oid = await _in_progress(client, team, refs)
    picture = jpeg_bytes(taken_at=utcnow(), mark=5)
    await _photo(client, team["master"], oid, "before", picture)
    await _photo(client, team["worker"], oid, "after", picture)
    detail = await _complete(
        client, team["worker"], oid, refs, "Заменено уплотнение, течь устранена"
    )
    photos = next(c for c in detail["assessment"]["checks"] if c["key"] == "photos")
    assert "не отличается от фото «до»" in photos["detail"]


# --- чистые правила -----------------------------------------------------------


def _facts(**overrides: Any) -> ClosureFacts:
    now = utcnow()
    base: dict[str, Any] = {
        "number": 147,
        "order_type": OrderType.UNPLANNED,
        "priority": Priority.HIGH,
        "equipment": "Насос гидравлический Н-7",
        "equipment_type": "Насос",
        "description": "Течь масла из-под уплотнения",
        "works_done": "Заменено уплотнение, течь устранена",
        "fault_code": "Г-02",
        "fault_name": "Течь гидравлической системы",
        "norm_hours": Decimal("1.5"),
        "norm_materials": (("Масло И-40А", "л", Decimal("1.5")),),
        "no_materials": False,
        "materials": (
            MaterialFact("Масло И-40А", "л", Decimal("1.5"), "смазочные", Decimal("1.5")),
        ),
        "after_photos": 1,
        "before_photos": 1,
        "issued_at": now - timedelta(hours=2),
        "started_at": now - timedelta(minutes=80),
        "done_at": now,
        "deadline_at": now + timedelta(hours=1),
    }
    base.update(overrides)
    return ClosureFacts(**base)


def test_clean_closure_passes_all_rules() -> None:
    checks = run_rules(_facts())
    assert [c.status for c in checks] == ["ok", "ok", "ok"]


def test_slow_work_and_missed_deadline() -> None:
    now = utcnow()
    check = check_time(
        _facts(started_at=now - timedelta(hours=4), deadline_at=now - timedelta(minutes=45))
    )
    assert check.status == "warn"
    assert check.items == [
        "Работа заняла 4 ч при нормативе 1 ч 30 мин (в 2,7 раза дольше).",
        "Срок нарушен на 45 мин.",
    ]


def test_material_from_wrong_category_is_flagged() -> None:
    cable = MaterialFact("Кабель КГ 3×16", "м", Decimal("10"), "электрика", None)
    check = check_materials(_facts(materials=(cable,)))
    assert check.status == "warn"
    assert "не типичен для шифра Г-02" in check.detail


def test_mock_works_match_detects_mismatch() -> None:
    result = mock_works_match(_facts(works_done="Заменён кабель питания, замерена изоляция"))
    assert result.check.status == "fail"
    assert result.check.critical


def test_low_confidence_leaves_decision_to_master() -> None:
    checks = [CheckResult("works_match", "Работы", "ok", "ок")]
    result = aggregate(checks, confidence=0.5)
    assert result.verdict is None
    assert result.needs_master_review


def test_critical_problem_overrides_low_confidence() -> None:
    checks = [CheckResult("completeness", "Полнота", "fail", "Нет фото", critical=True, penalty=35)]
    assert aggregate(checks, confidence=0.4).verdict == Verdict.REWORK
