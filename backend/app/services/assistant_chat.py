"""Ассистент мастера в режиме живого диалога (ТЗ 6.7): модель ведёт разговор и сама
решает, какие данные посмотреть, — через инструменты поверх базы (function calling).

- Цифры модель берёт только из инструментов — не выдумывает их.
- Персональные данные в модель не уходят: ФИО в данных и в вопросах заменяются метками
  «Сотрудник-N», а в готовом ответе метки возвращаются фамилиями.
- Без модели или при сбое отвечает ассистент на правилах (`assistant.ask`) — ответ есть всегда.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Employee, Equipment, Order, Section
from app.models.base import utcnow
from app.models.enums import PRIORITY_LABELS, STATUS_LABELS, OrderStatus
from app.services import assistant as rules_assistant
from app.services import orders as order_svc
from app.services.analytics.insights import ask as ask_analytics
from app.services.llm import prompt
from app.services.llm.gateway import gemini_generate
from app.services.people import shift_people, shift_summary
from app.services.reports import builders
from app.services.reports.model import window

log = logging.getLogger(__name__)

MAX_STEPS = 6  # вызовов модели на один вопрос: инструменты + итоговый ответ
HISTORY = 12  # сколько последних реплик диалога передаём модели

SPECIALTIES = list(rules_assistant.SPECIALTIES)
STATES = {
    "free": "свободен",
    "busy": "в работе",
    "queue": "есть очередь",
    "off_shift": "не на смене",
}


@dataclass
class Turn:
    role: str  # user | assistant
    text: str


@dataclass
class ChatReply:
    text: str
    source: str  # llm | rules
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    items: list[dict[str, str]] = field(default_factory=list)
    report: dict[str, Any] | None = None


# --- Обезличивание ------------------------------------------------------------------------


class NameMask:
    """ФИО ↔ «Сотрудник-N». Фамилии в вопросах ловятся по основе (Ахметов, Ахметову, Ахметова)."""

    def __init__(self, people: list[Employee]) -> None:
        self._by_token = {f"Сотрудник-{p.id}": p.short_name for p in people}
        pairs: list[tuple[str, str]] = []
        for p in people:
            token = f"Сотрудник-{p.id}"
            pairs += [(p.full_name, token), (p.short_name, token)]
        self._exact = sorted(pairs, key=lambda x: -len(x[0]))
        self._stems = []
        for p in people:
            surname = p.full_name.split()[0]
            if len(surname) >= 4:
                stem = surname[:-1] if len(surname) > 5 else surname
                self._stems.append(
                    (re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE), f"Сотрудник-{p.id}")
                )

    def hide(self, text: str) -> str:
        for name, token in self._exact:
            text = text.replace(name, token)
        for pattern, token in self._stems:
            text = pattern.sub(token, text)
        return text

    def show(self, text: str) -> str:
        return re.sub(
            r"Сотрудник-(\d+)", lambda m: self._by_token.get(m.group(0), "сотрудник"), text
        )

    def employee_id(self, token: str | None) -> int | None:
        match = re.fullmatch(r"\s*Сотрудник-(\d+)\s*", token or "")
        return int(match.group(1)) if match else None


# --- Инструменты --------------------------------------------------------------------------

S = {"type": "STRING"}
I = {"type": "INTEGER"}  # noqa: E741

TOOLS: list[dict[str, Any]] = [
    {
        "name": "shift_people",
        "description": (
            "Люди текущей смены: кто свободен, кто в работе (номер наряда), у кого очередь, кто "
            "не на смене."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "specialty": {
                    **S,
                    "enum": SPECIALTIES,
                    "description": "специальность, если спросили про неё",
                },
                "state": {**S, "enum": list(STATES), "description": "фильтр по состоянию"},
            },
        },
    },
    {
        "name": "shift_summary",
        "description": (
            "Счётчики текущей смены: выдано, выполнено, просрочено, отклонено, оборудование в "
            "простое."
        ),
    },
    {
        "name": "orders",
        "description": (
            "Наряды: активные, просроченные, на проверке ИИ или закрытые. Можно сузить по "
            "участку, оборудованию, исполнителю."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group": {
                    **S,
                    "enum": ["active", "overdue", "review", "closed"],
                    "description": "какие наряды",
                },
                "section": {**S, "description": "название участка"},
                "equipment": {**S, "description": "название или инвентарный номер оборудования"},
                "employee": {**S, "description": "метка сотрудника вида «Сотрудник-12»"},
                "limit": {**I, "description": "сколько строк, по умолчанию 15"},
            },
        },
    },
    {
        "name": "order_details",
        "description": (
            "Карточка наряда по номеру: описание, статус, исполнитель, срок, ход работ, "
            "комментарии, оценка ИИ."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {"number": {**I, "description": "номер наряда"}},
            "required": ["number"],
        },
    },
    {
        "name": "report",
        "description": "Отчёт по нарядам за период с ключевыми цифрами и сводкой.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "period": {**S, "enum": ["shift", "day", "week", "month"]},
                "section": {**S, "description": "название участка"},
            },
            "required": ["period"],
        },
    },
    {
        "name": "analytics",
        "description": (
            "Закономерности в истории нарядов за 3 месяца: проблемное оборудование, повторы, "
            "поломки после ППР, ночные отказы, перерасход, рост поломок. Передай вопрос "
            "пользователя своими словами."
        ),
        "parameters": {"type": "OBJECT", "properties": {"question": S}, "required": ["question"]},
    },
    {
        "name": "equipment_history",
        "description": (
            "История оборудования: сколько нарядов, внеплановых, простой, последние ремонты."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {"equipment": {**S, "description": "название или инв. номер"}},
            "required": ["equipment"],
        },
    },
]


class Toolbox:
    def __init__(self, session: AsyncSession, user: Employee, mask: NameMask) -> None:
        self.session = session
        self.user = user
        self.mask = mask
        self.report: dict[str, Any] | None = None

    async def run(self, name: str, args: dict[str, Any]) -> Any:
        handler = getattr(self, f"t_{name}", None)
        if handler is None:
            return {"ошибка": f"нет инструмента {name}"}
        try:
            return await handler(**args)
        except TypeError:
            return {"ошибка": "неверные параметры"}

    async def _section_id(self, name: str | None) -> int | None:
        if not name:
            return None
        stem = name.strip().lower()[:6]
        sections = list(await self.session.scalars(select(Section)))
        found = next(
            (s for s in sections if s.name.lower().startswith(stem) or stem in s.name.lower()), None
        )
        return found.id if found else None

    async def _equipment(self, query: str | None) -> Equipment | None:
        if not query:
            return None
        q = query.strip()
        return await self.session.scalar(
            select(Equipment)
            .where(or_(Equipment.inv_number.ilike(q), Equipment.name.ilike(f"%{q}%")))
            .limit(1)
        )

    async def t_shift_people(self, specialty: str | None = None, state: str | None = None) -> Any:
        people = await shift_people(self.session)
        rows = []
        for p in people:
            if specialty and p.employee.specialty != specialty:
                continue
            if state and p.state != state:
                continue
            rows.append(
                {
                    "кто": p.employee.short_name,
                    "специальность": p.employee.specialty,
                    "состояние": STATES.get(p.state, p.state),
                    "наряд": p.current_order.number if p.current_order else None,
                    "в очереди": p.queue_count,
                }
            )
        return rows

    async def t_shift_summary(self) -> Any:
        s = await shift_summary(self.session)
        return {
            "выдано": s.issued,
            "выполнено": s.done,
            "просрочено": s.overdue,
            "отклонено": s.rejected,
            "оборудование в простое": s.equipment_down,
        }

    async def t_orders(
        self,
        group: str = "active",
        section: str | None = None,
        equipment: str | None = None,
        employee: str | None = None,
        limit: int = 15,
    ) -> Any:
        f = order_svc.OrderFilters(sort="urgency", limit=max(1, min(int(limit or 15), 40)))
        if group == "overdue":
            f.active, f.overdue = True, True
        elif group == "review":
            f.statuses = [OrderStatus.DONE, OrderStatus.AI_REVIEW]
        elif group == "closed":
            f.statuses, f.sort = [OrderStatus.CLOSED], "recent"
        else:
            f.active = True
        f.section_id = await self._section_id(section)
        eq = await self._equipment(equipment)
        f.equipment_id = eq.id if eq else None
        f.assignee_id = self.mask.employee_id(employee)
        items = await order_svc.list_orders(self.session, self.user, f)
        return [
            {
                "номер": o.number,
                "оборудование": f"{o.equipment.inv_number} {o.equipment.name}",
                "участок": o.section.name,
                "приоритет": PRIORITY_LABELS[o.priority],
                "статус": STATUS_LABELS[o.status],
                "исполнитель": o.assignee.short_name if o.assignee else "не назначен",
                "срок": order_svc.local_datetime(o.deadline_at),
                "просрочен на мин": o.overdue_minutes or None,
                "оценка ИИ": o.ai_score,
                "описание": o.description[:160],
            }
            for o in items
        ]

    async def t_order_details(self, number: int) -> Any:
        order = await self.session.scalar(select(Order).where(Order.number == int(number)))
        if order is None:
            return {"ошибка": f"наряда №{number} нет"}
        d = await order_svc.order_detail(self.session, order.id, self.user)
        return {
            "номер": d.number,
            "оборудование": f"{d.equipment.inv_number} {d.equipment.name}",
            "участок": d.section.name,
            "приоритет": PRIORITY_LABELS[d.priority],
            "статус": STATUS_LABELS[d.status],
            "описание": d.description,
            "исполнитель": d.assignee.short_name if d.assignee else None,
            "мастер": d.master.short_name,
            "срок": order_svc.local_datetime(d.deadline_at),
            "выполненные работы": d.works_done,
            "шифр": f"{d.fault_code.code} {d.fault_code.name}" if d.fault_code else None,
            "простой мин": d.downtime_minutes,
            "оценка ИИ": d.assessment.final_score if d.assessment else None,
            "вердикт ИИ": d.assessment.explanation_master if d.assessment else None,
            "ход работ": [
                {
                    "когда": order_svc.local_datetime(e.created_at),
                    "кто": e.actor.short_name if e.actor else "система",
                    "действие": STATUS_LABELS.get(e.to_status, e.action)
                    if e.to_status
                    else e.action,
                    "причина": e.reason,
                    "комментарий": e.comment,
                }
                for e in d.events[-12:]
            ],
        }

    async def t_report(self, period: str = "week", section: str | None = None) -> Any:
        if period not in ("shift", "day", "week", "month"):
            period = "week"
        section_id = await self._section_id(section)
        w = window(period)  # type: ignore[arg-type]
        r = await builders.orders_report(
            self.session, w, builders.ReportFilter(section_id=section_id)
        )
        self.report = {"kind": "orders", "period": period, "section_id": section_id}
        return {
            "период": w.label,
            "срез": r.filters,
            "показатели": {k.label: k.value for k in r.kpis},
            "сводка": r.summary,
            "по исполнителям": r.tables[1].rows[:10] if len(r.tables) > 1 else [],
        }

    async def t_analytics(self, question: str = "") -> Any:
        answer = await ask_analytics(self.session, question or "проблемы за месяц")
        return {
            "охват": answer.scope_label,
            "находки": [
                {
                    "что": i.finding.title,
                    "о ком/чём": i.finding.subject,
                    "важность": i.finding.severity,
                    "факты": i.finding.facts,
                    "вывод": i.conclusion,
                    "рекомендация": i.recommendation,
                }
                for i in answer.items
            ],
        }

    async def t_equipment_history(self, equipment: str = "") -> Any:
        eq = await self._equipment(equipment)
        if eq is None:
            return {"ошибка": f"оборудование «{equipment}» не найдено"}
        items = await order_svc.list_orders(
            self.session, self.user, order_svc.OrderFilters(equipment_id=eq.id, limit=200)
        )
        unplanned = [o for o in items if o.type.value == "unplanned"]
        return {
            "оборудование": f"{eq.inv_number} {eq.name}",
            "нарядов": len(items),
            "внеплановых": len(unplanned),
            "последние": [
                {
                    "номер": o.number,
                    "дата": order_svc.local_datetime(o.created_at),
                    "тип": "внеплановый" if o.type.value == "unplanned" else "плановый",
                    "статус": STATUS_LABELS[o.status],
                    "описание": o.description[:120],
                }
                for o in items[:10]
            ],
        }


# --- Диалог -------------------------------------------------------------------------------


def _system(now: datetime) -> str:
    return (
        prompt("assistant_chat") + f"\n\nСейчас: {order_svc.local_datetime(now)} (время Костаная)."
    )


def _text_of(parts: list[dict[str, Any]]) -> str:
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


async def chat(session: AsyncSession, user: Employee, turns: list[Turn]) -> ChatReply:
    question = next((t.text for t in reversed(turns) if t.role == "user"), "").strip()
    if settings.llm_backend == "gemini" and question:
        try:
            reply = await _gemini_chat(session, user, turns[-HISTORY:])
        except Exception:  # ассистент не должен падать: при любой ошибке — правила
            log.exception("Ассистент: диалог с моделью не удался")
            reply = None
        if reply is not None:
            return reply
    fallback = await rules_assistant.ask(session, user, question)
    return ChatReply(
        text=fallback.text,
        source="rules",
        items=[asdict(i) for i in fallback.items],
        report=fallback.report,
    )


async def _gemini_chat(
    session: AsyncSession, user: Employee, turns: list[Turn]
) -> ChatReply | None:
    people = list(await session.scalars(select(Employee)))
    mask = NameMask(people)
    tools = Toolbox(session, user, mask)
    contents: list[dict[str, Any]] = [
        {
            "role": "model" if t.role == "assistant" else "user",
            "parts": [{"text": mask.hide(t.text)}],
        }
        for t in turns
        if t.text.strip()
    ]
    used: list[str] = []
    body_base = {
        "systemInstruction": {"parts": [{"text": _system(utcnow())}]},
        "tools": [{"functionDeclarations": TOOLS}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }
    for _step in range(MAX_STEPS):
        data = await gemini_generate("assistant_chat", {**body_base, "contents": contents})
        if data is None:
            return None
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        content = candidates[0].get("content") or {}
        parts: list[dict[str, Any]] = content.get("parts") or []
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if not calls:
            text = _text_of(parts)
            if not text:
                return None
            return ChatReply(
                text=mask.show(text),
                source="llm",
                model=settings.active_model(),
                tools=used,
                report=tools.report,
            )
        # Ответ модели кладём как есть (в нём подписи рассуждений), затем результаты инструментов
        contents.append({"role": "model", "parts": parts})
        responses = []
        for call in calls:
            name = str(call.get("name", ""))
            used.append(name)
            result = await tools.run(name, dict(call.get("args") or {}))
            masked = json.loads(mask.hide(json.dumps(result, ensure_ascii=False, default=str)))
            responses.append({"functionResponse": {"name": name, "response": {"result": masked}}})
        contents.append({"role": "user", "parts": responses})
    return None
