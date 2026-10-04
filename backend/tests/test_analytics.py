"""Аналитика: каждый детектор находит свою закономерность из CLAUDE.md (раздел 7).

Эталон — описание закономерностей в ТЗ (К-3 и М-02, Мельников, бригада №2 на КМД-1750,
обогащение ночью, Сейтказиев и смазочные), а не повторный расчёт тем же кодом. Для части
детекторов есть и обратная проверка: без закономерности в данных находки нет.
"""

from dataclasses import replace

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.services.analytics import Finding, run_detectors
from app.services.analytics.insights import rule_plan
from seed.history import HistoryConfig, PatternConfig
from tests.conftest import EmployeeFactory, auth_header
from tests.test_seed import _seed


def _by_kind(findings: list[Finding], kind: str) -> list[Finding]:
    return [f for f in findings if f.kind == kind]


async def test_problem_equipment_is_conveyor_k3_with_bearings(session: AsyncSession) -> None:
    await _seed(session)
    (top, *_) = _by_kind(await run_detectors(session), "problem_equipment")
    assert top.subject == "Конвейер К-3"
    assert top.numbers["ratio"] >= 2.5
    assert top.numbers["top_code"] == "М-02"
    assert "М-02" in top.facts and "в 3" in top.facts


async def test_without_k3_pattern_nothing_is_flagged_for_k3(session: AsyncSession) -> None:
    await _seed(session, HistoryConfig(patterns=replace(PatternConfig(), k3_multiplier=1.0)))
    subjects = [f.subject for f in _by_kind(await run_detectors(session), "problem_equipment")]
    assert "Конвейер К-3" not in subjects


async def test_worker_with_returns_is_melnikov(session: AsyncSession) -> None:
    await _seed(session)
    (top, *_) = _by_kind(await run_detectors(session), "worker_returns")
    assert top.subject == "Мельников И."
    assert 0.25 <= top.numbers["rate"] <= 0.4
    assert top.numbers["others_rate"] < 0.1


async def test_breakdowns_after_ppr_point_to_brigade_2_on_kmd(session: AsyncSession) -> None:
    await _seed(session)
    (top, *_) = _by_kind(await run_detectors(session), "after_ppr")
    assert top.subject == "Дробилка КМД-1750"
    assert top.numbers["brigade"] == "Бригада №2"
    assert top.numbers["share"] >= 0.6
    assert top.numbers["other_share"] <= 0.34


async def test_night_electrical_failures_in_beneficiation(session: AsyncSession) -> None:
    await _seed(session)
    (top, *_) = _by_kind(await run_detectors(session), "night_shift")
    assert top.subject == "Обогащение"
    assert top.numbers["group"] == "Э"
    assert top.numbers["ratio"] >= 2


async def test_lubricant_overuse_is_seitkaziev(session: AsyncSession) -> None:
    await _seed(session)
    (top, *_) = _by_kind(await run_detectors(session), "material_overuse")
    assert top.subject == "Сейтказиев М."
    assert top.numbers["category"] == "смазочные"
    assert 1.8 <= top.numbers["ratio"] <= 3


async def test_all_five_spec_patterns_found_in_one_run(session: AsyncSession) -> None:
    await _seed(session)
    kinds = {f.kind for f in await run_detectors(session)}
    assert {
        "problem_equipment",
        "worker_returns",
        "after_ppr",
        "night_shift",
        "material_overuse",
    } <= kinds


def test_free_text_question_is_parsed_without_model() -> None:
    sections = ["Дробление", "Обогащение", "Конвейерный транспорт", "Ремонтно-механический цех"]
    equipment = ["Конвейер К-3", "Дробилка КМД-1750", "Насос гидравлический Н-7"]

    plan = rule_plan("Покажи проблемы участка дробления за месяц", sections, equipment)
    assert (plan.section, plan.equipment, plan.days) == ("Дробление", None, 30)

    plan = rule_plan("Что с К-3 за неделю?", sections, equipment)
    assert (plan.equipment, plan.days) == ("Конвейер К-3", 7)

    plan = rule_plan("Перерасход материалов на конвейерном транспорте", sections, equipment)
    assert plan.section == "Конвейерный транспорт"
    assert plan.kinds == ["material_overuse"]


async def test_analytics_api_for_boss(
    client: AsyncClient, session: AsyncSession, make_employee: EmployeeFactory
) -> None:
    await _seed(session)
    boss = await make_employee(Role.BOSS, login="boss_t")
    worker = await make_employee(Role.WORKER, login="worker_t")

    resp = await client.get("/api/analytics", headers=auth_header(boss))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope_label"] == "всё предприятие, 90 дн."
    top = body["items"][0]
    assert top["severity"] == "high" and top["conclusion"] and top["recommendation"]
    assert top["source"] == "rules"  # без ключа — текст детектора

    resp = await client.post(
        "/api/analytics/ask", json={"question": "что с К-3 за месяц"}, headers=auth_header(boss)
    )
    answer = resp.json()
    assert answer["scope_label"] == "Конвейер К-3, 30 дн."
    assert any(i["subject"] == "Конвейер К-3" for i in answer["items"])

    assert (await client.get("/api/analytics", headers=auth_header(worker))).status_code == 403


async def test_weekly_digest_goes_to_boss_and_masters(session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.models import Notification
    from app.services.analytics.digest import weekly_digest

    await _seed(session)
    sent = await weekly_digest(session)
    await session.commit()
    notes = list(
        await session.scalars(select(Notification).where(Notification.kind == "weekly_digest"))
    )
    assert sent == len(notes) == 3  # руководитель и два мастера
    assert "Конвейер К-3" in notes[0].body
