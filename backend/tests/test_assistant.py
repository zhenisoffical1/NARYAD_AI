"""Ассистент мастера: разбор вопроса без модели и ответы с цифрами из базы."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.services.assistant import rule_plan
from tests.conftest import EmployeeFactory, auth_header
from tests.test_seed import _seed

SECTIONS = ["Дробление", "Обогащение", "Конвейерный транспорт", "Ремонтно-механический цех"]


@pytest.mark.parametrize(
    ("question", "intent", "specialty", "section", "period"),
    [
        ("Кто сейчас свободен из электриков?", "free_people", "электромонтёр", None, "shift"),
        ("Кого из слесарей можно отправить?", "free_people", "слесарь-ремонтник", None, "shift"),
        ("Что просрочено на смене?", "overdue", None, None, "shift"),
        ("Сформируй отчёт за неделю по участку обогащения", "report", None, "Обогащение", "week"),
        ("Покажи проблемы участка дробления за месяц", "analytics", None, "Дробление", "month"),
        ("Как дела на смене?", "shift", None, None, "shift"),
    ],
)
def test_rule_plan(
    question: str, intent: str, specialty: str | None, section: str | None, period: str
) -> None:
    plan = rule_plan(question, SECTIONS)
    assert (plan.intent, plan.specialty, plan.section, plan.period) == (
        intent,
        specialty,
        section,
        period,
    )


@pytest.fixture
async def master(session: AsyncSession, make_employee: EmployeeFactory):  # type: ignore[no-untyped-def]
    await _seed(session)
    return await make_employee(Role.MASTER, login="master_a")


async def ask(client: AsyncClient, user, question: str) -> dict:  # type: ignore[no-untyped-def,type-arg]
    resp = await client.post(
        "/api/assistant/ask", json={"question": question}, headers=auth_header(user)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


async def test_free_people_by_specialty(client: AsyncClient, master) -> None:  # type: ignore[no-untyped-def]
    reply = await ask(client, master, "Кто свободен из слесарей?")
    assert reply["intent"] == "free_people" and reply["source"] == "rules"
    assert reply["text"].startswith("Свободны")
    assert any(i["tone"] == "ok" for i in reply["items"])


async def test_overdue_report_and_analytics(client: AsyncClient, master) -> None:  # type: ignore[no-untyped-def]
    overdue = await ask(client, master, "Что просрочено?")
    assert overdue["intent"] == "overdue" and overdue["text"]

    report = await ask(client, master, "Отчёт за неделю по обогащению")
    assert report["intent"] == "report"
    assert report["report"]["period"] == "week" and report["report"]["section_id"]
    assert "Выдано" in [i["title"] for i in report["items"]]

    problems = await ask(client, master, "Какие проблемы на конвейерном транспорте за месяц?")
    assert problems["intent"] == "analytics"
    assert any("К-3" in i["title"] for i in problems["items"]), problems


async def test_worker_has_no_assistant(client: AsyncClient, make_employee: EmployeeFactory) -> None:
    worker = await make_employee(Role.WORKER, login="w_a")
    resp = await client.post(
        "/api/assistant/ask", json={"question": "кто свободен"}, headers=auth_header(worker)
    )
    assert resp.status_code == 403
