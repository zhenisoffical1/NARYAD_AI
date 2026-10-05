"""Ассистент мастера (ТЗ 6.7): вопросы о смене простым языком.

Модель только разбирает вопрос в план (что спросили, про какую специальность, участок, период) —
ей уходят вопрос и справочники, без ФИО. Ответ с цифрами и фамилиями собирают правила из базы,
поэтому он точный и не уходит во внешний сервис. Без ключа работает разбор по словам.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Section
from app.services import orders as order_svc
from app.services.analytics.insights import ask as ask_analytics
from app.services.llm import ask_json, facts_json, prompt, text_block
from app.services.people import shift_people, shift_summary
from app.services.reports import builders
from app.services.reports.model import Period, window

Intent = Literal["free_people", "overdue", "shift", "report", "analytics"]

SPECIALTIES = {
    "слесарь-ремонтник": ("слесар", "механик"),
    "электромонтёр": ("электрик", "электромонт", "электро"),
    "электрогазосварщик": ("сварщ", "сварк"),
}


class Plan(BaseModel):
    intent: Intent
    specialty: str | None
    section: str | None
    period: Literal["shift", "day", "week", "month"]


@dataclass
class Item:
    title: str
    subtitle: str = ""
    tone: Literal["ok", "work", "queue", "danger", "info"] = "info"


@dataclass
class Reply:
    question: str
    intent: Intent
    text: str
    items: list[Item] = field(default_factory=list)
    report: dict[str, str | int | None] | None = None  # параметры отчёта для перехода
    source: str = "rules"


_PERIOD_WORDS: tuple[tuple[str, Period], ...] = (
    ("недел", "week"),
    ("месяц", "month"),
    ("сутк", "day"),
    ("сегодня", "day"),
    ("смен", "shift"),
)


def _stem(name: str) -> str:
    word = name.split()[0].lower()
    return word[:-2] if len(word) > 5 else word


def rule_plan(question: str, sections: list[str]) -> Plan:
    q = question.lower().replace("ё", "е")
    specialty = next(
        (name for name, words in SPECIALTIES.items() if any(w in q for w in words)), None
    )
    section = next((s for s in sections if _stem(s).replace("ё", "е") in q), None)
    period: Period = next((p for w, p in _PERIOD_WORDS if w in q), "shift")
    intent: Intent
    if re.search(r"свобод|не занят|кого.*(послать|отправить|дать|поставить)|кто может", q):
        intent = "free_people"
    elif re.search(r"просроч|опазд|не успева|сорван", q):
        intent = "overdue"
    elif re.search(r"отч[её]т|сводк|итог", q):
        intent = "report"
    elif re.search(r"проблем|аномал|ломает|поломк|закономер|рекоменд|почему", q):
        intent = "analytics"
    else:
        intent = "shift"
    if intent == "report" and period == "shift" and "смен" not in q:
        period = "week"
    return Plan(intent=intent, specialty=specialty, section=section, period=period)


async def ask(session: AsyncSession, user: Employee, question: str) -> Reply:
    sections = {s.name: s.id for s in await session.scalars(select(Section))}
    plan = await ask_json(
        "assistant_plan",
        Plan,
        system=prompt("assistant_plan"),
        content=[
            text_block(
                facts_json(
                    {
                        "вопрос": question,
                        "участки": list(sections),
                        "специальности": list(SPECIALTIES),
                    }
                )
            )
        ],
        fast=True,
    )
    source = "llm"
    if (
        plan is None
        or (plan.section and plan.section not in sections)
        or (plan.specialty and plan.specialty not in SPECIALTIES)
    ):
        plan = rule_plan(question, list(sections))
        source = "rules"

    section_id = sections.get(plan.section) if plan.section else None
    if plan.intent == "free_people":
        reply = await _free_people(session, plan.specialty)
    elif plan.intent == "overdue":
        reply = await _overdue(session, user, section_id)
    elif plan.intent == "report":
        reply = await _report(session, plan.period, section_id, plan.section)
    elif plan.intent == "analytics":
        reply = await _analytics(session, question)
    else:
        reply = await _shift(session)
    reply.question = question
    reply.source = source
    return reply


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


async def _free_people(session: AsyncSession, specialty: str | None) -> Reply:
    people = await shift_people(session)
    if specialty:
        people = [p for p in people if p.employee.specialty == specialty]
    who = {
        "слесарь-ремонтник": "слесарей",
        "электромонтёр": "электромонтёров",
        "электрогазосварщик": "сварщиков",
    }.get(specialty or "", "исполнителей")
    free = [p for p in people if p.state == "free"]
    busy = [p for p in people if p.state in ("busy", "queue")]
    if free:
        names = ", ".join(p.employee.short_name for p in free)
        text = f"Свободны {len(free)} из {len(people)} {who} на смене: {names}."
    elif busy:
        text = (
            f"Свободных {who} сейчас нет. Заняты: "
            + ", ".join(
                f"{p.employee.short_name} (№{p.current_order.number})"
                if p.current_order
                else p.employee.short_name
                for p in busy
            )
            + "."
        )
    else:
        text = f"{who.capitalize()} на смене нет."
    items = [Item(p.employee.short_name, p.employee.specialty or "", "ok") for p in free] + [
        Item(
            p.employee.short_name,
            (f"в работе №{p.current_order.number}" if p.current_order else "в работе")
            + (f", очередь {p.queue_count}" if p.queue_count else ""),
            "queue" if p.state == "queue" else "work",
        )
        for p in busy
    ]
    return Reply("", "free_people", text, items)


async def _overdue(session: AsyncSession, user: Employee, section_id: int | None) -> Reply:
    orders = await order_svc.list_orders(
        session,
        user,
        order_svc.OrderFilters(active=True, overdue=True, section_id=section_id, sort="urgency"),
    )
    orders.sort(key=lambda o: -o.overdue_minutes)
    if not orders:
        return Reply("", "overdue", "Просроченных нарядов нет.")
    word = _plural(len(orders), "наряд", "наряда", "нарядов")
    first = orders[0]
    text = (
        f"Просрочено {len(orders)} {word}. Дольше всех — №{first.number}, {first.equipment.name}."
    )
    items = [
        Item(
            f"№{o.number} {o.equipment.name}",
            f"{o.assignee.short_name if o.assignee else 'без исполнителя'}, "
            f"просрочен на {_minutes(o.overdue_minutes)}",
            "danger",
        )
        for o in orders
    ]
    return Reply("", "overdue", text, items)


def _minutes(m: int) -> str:
    return f"{m // 60} ч {m % 60} мин" if m >= 60 else f"{m} мин"


async def _shift(session: AsyncSession) -> Reply:
    s = await shift_summary(session)
    text = (
        f"За смену выдано {s.issued}, выполнено {s.done}, просрочено {s.overdue}, "
        f"отклонено {s.rejected}. Оборудование в простое: {s.equipment_down}."
    )
    return Reply("", "shift", text)


async def _report(
    session: AsyncSession, period: Period, section_id: int | None, section: str | None
) -> Reply:
    w = window(period)
    report = await builders.orders_report(session, w, builders.ReportFilter(section_id=section_id))
    where = f", участок «{section}»" if section else ""
    items = [
        Item(k.label, k.value, "danger" if k.tone == "danger" else "info") for k in report.kpis
    ]
    return Reply(
        "",
        "report",
        f"{w.label}{where}. {report.summary or ''}".strip(),
        items,
        report={"kind": "orders", "period": period, "section_id": section_id},
    )


async def _analytics(session: AsyncSession, question: str) -> Reply:
    answer = await ask_analytics(session, question)
    if not answer.items:
        return Reply(
            "", "analytics", f"По запросу ({answer.scope_label}) закономерностей не найдено."
        )
    items = [
        Item(
            f"{i.finding.title}: {i.finding.subject}",
            i.recommendation,
            "danger" if i.finding.severity == "high" else "info",
        )
        for i in answer.items
    ]
    return Reply("", "analytics", f"{answer.scope_label}. {answer.items[0].conclusion}", items)
