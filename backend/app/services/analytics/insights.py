"""Выводы и рекомендации по находкам, запрос к аналитике свободным текстом.

Цифры всегда из детекторов. Модель (если есть ключ) только переписывает вывод проще и
уточняет рекомендацию; без ключа — шаблонный текст детектора. Фамилии в модель не уходят:
исполнитель заменяется меткой [ИСП-N] и восстанавливается в ответе.
"""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Equipment, Section
from app.services.analytics import run_detectors
from app.services.analytics.data import Scope
from app.services.analytics.detectors import Finding
from app.services.llm import ask_json, facts_json, prompt, text_block

MAX_EXPLAINED = 8
KINDS = (
    "problem_equipment",
    "worker_returns",
    "after_ppr",
    "night_shift",
    "material_overuse",
    "repeat_fault",
    "growth_trend",
)


class _Insight(BaseModel):
    conclusion: str = Field(max_length=600)
    recommendation: str = Field(max_length=400)


class _Insights(BaseModel):
    items: list[_Insight]


@dataclass
class Explained:
    finding: Finding
    conclusion: str
    recommendation: str
    source: str  # llm | rules


def _mask(findings: list[Finding]) -> tuple[list[str], dict[str, str]]:
    """Факты для модели без фамилий: исполнитель → [ИСП-N]."""
    tokens: dict[str, str] = {}
    texts = []
    for f in findings:
        text = f.facts
        if "worker_id" in f.refs:
            token = tokens.setdefault(f.subject, f"[ИСП-{len(tokens) + 1}]")
            text = text.replace(f.subject, token)
        texts.append(text)
    return texts, {token: name for name, token in tokens.items()}


def _unmask(text: str, names: dict[str, str]) -> str:
    for token, name in names.items():
        text = text.replace(token, name)
    return text


async def explain(findings: list[Finding]) -> list[Explained]:
    top = findings[:MAX_EXPLAINED]
    texts, names = _mask(top)
    out = None
    if top:
        out = await ask_json(
            "insights",
            _Insights,
            system=prompt("insights"),
            content=[
                text_block(
                    facts_json(
                        [{"находка": f.title, "факты": t} for f, t in zip(top, texts, strict=True)]
                    )
                )
            ],
        )
    if out is not None and len(out.items) == len(top):
        return [
            Explained(f, _unmask(i.conclusion, names), _unmask(i.recommendation, names), "llm")
            for f, i in zip(top, out.items, strict=True)
        ] + [Explained(f, f.facts, f.recommendation, "rules") for f in findings[MAX_EXPLAINED:]]
    return [Explained(f, f.facts, f.recommendation, "rules") for f in findings]


# --- запрос свободным текстом ---------------------------------------------------------------


class Plan(BaseModel):
    days: int = Field(ge=1, le=365)
    section: str | None
    equipment: str | None
    kinds: list[str]


@dataclass
class Answer:
    question: str
    scope_label: str
    days: int
    section_id: int | None
    equipment_id: int | None
    items: list[Explained] = field(default_factory=list)
    source: str = "rules"


_PERIODS = (
    (re.compile(r"недел"), 7),
    (re.compile(r"сутк|сегодня"), 1),
    (re.compile(r"квартал|три месяц|3 месяц|90"), 90),
    (re.compile(r"месяц|30"), 30),
)

_KIND_WORDS = {
    "problem_equipment": ("проблемн", "чаще всего", "ломается", "поломк"),
    "worker_returns": ("возврат", "доработк", "исполнител", "кто плохо"),
    "after_ppr": ("ппр", "после ремонт", "планов"),
    "night_shift": ("ноч", "по сменам", "смена"),
    "material_overuse": ("материал", "перерасход", "смазк", "масл", "списан"),
    "repeat_fault": ("повтор",),
    "growth_trend": ("рост", "риск", "прогноз", "тренд"),
}


def _stem(name: str) -> str:
    """«Конвейерный транспорт» → «конвейерн»: ловит и «конвейерного транспорта»."""
    word = name.split()[0].lower()
    return word[:-2] if len(word) > 5 else word


def rule_plan(question: str, sections: list[str], equipment: list[str]) -> Plan:
    """Разбор вопроса без модели: период, участок, оборудование и виды находок по словам."""
    q = question.lower()
    days = next((d for pattern, d in _PERIODS if pattern.search(q)), 30)
    section = next((s for s in sections if _stem(s) in q), None)
    found = None
    for name in equipment:
        # «К-3», «Н-7», «КМД-1750» — по обозначению модели, иначе по полному названию
        code = name.split()[-1].lower()
        if (len(code) >= 3 and re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", q)) or (
            name.lower() in q
        ):
            found = name
            break
    kinds = [k for k, words in _KIND_WORDS.items() if any(w in q for w in words)]
    return Plan(days=days, section=section, equipment=found, kinds=kinds)


async def ask(session: AsyncSession, question: str, *, llm: bool = True) -> Answer:
    """llm=False — без вызовов модели: план по словам, выводы правилами (инструмент ассистента)."""
    sections = {s.name: s.id for s in await session.scalars(select(Section))}
    equipment = {e.name: e.id for e in await session.scalars(select(Equipment))}

    plan = (
        None
        if not llm
        else await ask_json(
            "analytics_plan",
            Plan,
            system=prompt("analytics_plan"),
            content=[
                text_block(
                    facts_json(
                        {
                            "вопрос": question,
                            "участки": list(sections),
                            "оборудование": list(equipment),
                        }
                    )
                )
            ],
            fast=True,
        )
    )
    source = "llm" if plan is not None else "rules"
    if (
        plan is None
        or (plan.section and plan.section not in sections)
        or (plan.equipment and plan.equipment not in equipment)
    ):
        plan = rule_plan(question, list(sections), list(equipment))
        source = "rules"

    scope = Scope(
        days=plan.days,
        section_id=sections.get(plan.section) if plan.section else None,
        equipment_id=equipment.get(plan.equipment) if plan.equipment else None,
    )
    findings = await run_detectors(session, scope)
    kinds = [k for k in plan.kinds if k in KINDS]
    if kinds:
        findings = [f for f in findings if f.kind in kinds]

    where = plan.equipment or (f"участок «{plan.section}»" if plan.section else "всё предприятие")
    items = (
        await explain(findings)
        if llm
        else [Explained(f, f.facts, f.recommendation, "rules") for f in findings]
    )
    return Answer(
        question=question,
        scope_label=f"{where}, {plan.days} дн.",
        days=plan.days,
        section_id=scope.section_id,
        equipment_id=scope.equipment_id,
        items=items,
        source="llm" if source == "llm" or any(i.source == "llm" for i in items) else "rules",
    )
