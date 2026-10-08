"""Ассистент мастера: разбор вопроса без модели и ответы с цифрами из базы."""

import json

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


# --- Живой диалог с моделью (Gemini, function calling) ------------------------------------


def _model_says(*parts: dict) -> tuple[int, dict]:  # type: ignore[type-arg]
    return 200, {"candidates": [{"content": {"role": "model", "parts": list(parts)}}]}


@pytest.fixture
def gemini(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    from app.config import settings
    from app.services.llm import gateway

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    sent: list[dict] = []  # type: ignore[type-arg]

    def install(*replies: tuple[int, dict]) -> list[dict]:  # type: ignore[type-arg]
        queue = list(replies)

        async def fake(model: str, body: dict, wait_seconds: float | None = None):  # type: ignore[no-untyped-def,type-arg]
            sent.append(body)
            return queue.pop(0)

        monkeypatch.setattr(gateway, "_gemini_post", fake)
        return sent

    return install


async def chat(client: AsyncClient, user, *texts: str) -> dict:  # type: ignore[no-untyped-def,type-arg]
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "text": t} for i, t in enumerate(texts)
    ]
    resp = await client.post(
        "/api/assistant/chat", json={"messages": messages}, headers=auth_header(user)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


async def test_chat_without_key_answers_by_rules(client: AsyncClient, master) -> None:  # type: ignore[no-untyped-def]
    reply = await chat(client, master, "Кто свободен из слесарей?")
    assert reply["source"] == "rules" and reply["text"].startswith("Свободны")


async def test_chat_model_uses_tools_and_never_sees_names(  # type: ignore[no-untyped-def]
    client: AsyncClient, master, gemini, session: AsyncSession
) -> None:
    from sqlalchemy import select

    from app.models import Employee

    akhmetov = await session.scalar(select(Employee).where(Employee.login == "akhmetov"))
    assert akhmetov is not None
    token = f"Сотрудник-{akhmetov.id}"
    sent = gemini(
        _model_says(
            {"functionCall": {"name": "shift_people", "args": {"specialty": "слесарь-ремонтник"}}}
        ),
        _model_says({"text": f"Свободен {token}, можно отправить его на насос."}),
    )
    reply = await chat(client, master, "Что сейчас делает Ахметов и кого из слесарей отправить?")

    assert reply["source"] == "llm" and reply["tools"] == ["shift_people"]
    assert "Ахметов Е." in reply["text"] and "Сотрудник-" not in reply["text"]

    everything_sent = json.dumps(sent, ensure_ascii=False)
    assert "Ахметов" not in everything_sent, "фамилии не должны уходить в модель"
    assert token in everything_sent
    tool_turn = sent[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert tool_turn["name"] == "shift_people" and tool_turn["response"]["result"]
    assert sent[0]["tools"][0]["functionDeclarations"]


async def test_chat_falls_back_to_rules_when_model_fails(
    client: AsyncClient, master, gemini
) -> None:  # type: ignore[no-untyped-def]
    failure = (500, {"error": {"message": "internal"}})
    gemini(failure, failure)  # диалог и разбор вопроса правилами — оба без модели
    reply = await chat(client, master, "Что просрочено?")
    assert reply["source"] == "rules" and reply["text"]


def test_name_mask_round_trip() -> None:
    from types import SimpleNamespace

    from app.services.assistant_chat import NameMask

    people = [SimpleNamespace(id=7, full_name="Ахметов Ерлан Каиртаевич", short_name="Ахметов Е.")]
    mask = NameMask(people)  # type: ignore[arg-type]
    hidden = mask.hide("Позвони Ахметову, а Ахметов Е. пусть ждёт")
    assert "Ахметов" not in hidden and hidden.count("Сотрудник-7") == 2
    assert mask.show("Отправьте Сотрудник-7") == "Отправьте Ахметов Е."
    assert mask.employee_id("Сотрудник-7") == 7
