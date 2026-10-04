"""Подсказки мастеру при выдаче наряда: кого назначить и какой шифр (ТЗ 5.1.3–5.1.4, CLAUDE 6.6).

Порядок подбора: нужная специальность → свободен → лучшая оценка по этому типу
оборудования → меньше очередь. Специальность важнее занятости: свободный сварщик
не починит двигатель. Каждая рекомендация объясняется одной строкой.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import Invalid
from app.models import Employee, Equipment, FaultCode, Order
from app.models.base import utcnow
from app.models.enums import OrderStatus, OrderType, Priority
from app.schemas.orders import PersonStatus
from app.services.orders import default_deadline_hours, latest_assessments
from app.services.people import shift_people
from app.services.verification.topics import topics_of, weighted_overlap

SLESAR = "слесарь-ремонтник"
ELECTRIC = "электромонтёр"
WELDER = "электрогазосварщик"

ELECTRIC_TOPICS = {"электродвигатель", "пускатель/автомат", "кабель", "защита/КЗ", "датчик"}
WELD_TOPICS = {"металлоконструкция"}

STATE_RANK = {"free": 0, "queue": 1, "busy": 2, "off_shift": 3}


@dataclass
class Candidate:
    person: PersonStatus
    specialty: str | None
    grade: int | None
    specialty_match: bool
    equipment_score: float | None
    reason: str
    recommended: bool = False


@dataclass
class FaultSuggestion:
    id: int
    code: str
    name: str
    norm_hours: Decimal | None
    confidence: float


@dataclass
class Assist:
    specialty: str
    fault_code: FaultSuggestion | None
    order_type: OrderType
    deadline_hours: float
    candidates: list[Candidate]


def needed_specialty(description: str) -> str:
    topics = topics_of(description)
    if topics & ELECTRIC_TOPICS:
        return ELECTRIC
    if topics & WELD_TOPICS and len(topics) == 1:
        return WELDER
    return SLESAR


async def suggest_fault_code(
    session: AsyncSession, description: str, equipment: Equipment
) -> FaultSuggestion | None:
    problem = topics_of(description)
    if not problem:
        return None
    codes = list(await session.scalars(select(FaultCode).options(selectinload(FaultCode.norm))))
    history = Counter(
        await session.scalars(
            select(Order.fault_code_id).where(
                Order.equipment_id == equipment.id,
                Order.type == OrderType.UNPLANNED,
                Order.fault_code_id.is_not(None),
                Order.created_at >= utcnow() - timedelta(days=180),
            )
        )
    )
    total = sum(history.values()) or 1

    best: tuple[float, FaultCode] | None = None
    for code in codes:
        match = weighted_overlap(problem, topics_of(code.name))
        if not match:
            continue
        score = match * 2 + history.get(code.id, 0) / total
        if best is None or score > best[0]:
            best = (score, code)
    if best is None:
        return None
    score, code = best
    return FaultSuggestion(
        id=code.id,
        code=code.code,
        name=code.name,
        norm_hours=code.norm.norm_hours if code.norm else None,
        confidence=round(min(0.95, score / 2.5), 2),
    )


async def _equipment_type_scores(session: AsyncSession, equipment_type: str) -> dict[int, float]:
    """Средняя итоговая оценка каждого исполнителя по оборудованию этого типа за 90 дней."""
    orders = list(
        await session.scalars(
            select(Order)
            .join(Equipment, Equipment.id == Order.equipment_id)
            .where(
                Equipment.type == equipment_type,
                Order.status == OrderStatus.CLOSED,
                Order.closed_at >= utcnow() - timedelta(days=90),
                Order.assignee_id.is_not(None),
            )
        )
    )
    assessments = await latest_assessments(session, [o.id for o in orders])
    scores: dict[int, list[int]] = defaultdict(list)
    for order in orders:
        assessment = assessments.get(order.id)
        if order.assignee_id and assessment and assessment.final_score is not None:
            scores[order.assignee_id].append(assessment.final_score)
    return {wid: sum(s) / len(s) for wid, s in scores.items() if len(s) >= 2}


def _state_text(person: PersonStatus) -> str:
    if person.state == "free":
        return "свободен"
    if person.state == "queue":
        return f"очередь {person.queue_count}"
    if person.state == "busy":
        number = person.current_order.number if person.current_order else None
        return f"в работе №{number}" if number else "в работе"
    return "не на смене"


async def assist(
    session: AsyncSession, equipment_id: int, description: str, priority: Priority | None
) -> Assist:
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise Invalid("Оборудование не найдено в справочнике.")

    priority = priority or Priority.NORMAL
    specialty = needed_specialty(description)
    fault = await suggest_fault_code(session, description, equipment)
    if fault and fault.code[0] == "Э":
        specialty = ELECTRIC

    people = await shift_people(session)
    employees = {
        e.id: e
        for e in await session.scalars(
            select(Employee).where(Employee.id.in_([p.employee.id for p in people]))
        )
    }
    type_scores = await _equipment_type_scores(session, equipment.type)

    candidates = []
    for person in people:
        employee = employees[person.employee.id]
        match = employee.specialty == specialty
        score = type_scores.get(employee.id)
        parts = [_state_text(person), employee.specialty or "специальность не указана"]
        if score is not None:
            parts.append(f"оценка по типу «{equipment.type}» — {round(score)}")
        candidates.append(
            Candidate(
                person=person,
                specialty=employee.specialty,
                grade=employee.grade,
                specialty_match=match,
                equipment_score=round(score, 1) if score is not None else None,
                reason=" · ".join(parts),
            )
        )

    candidates.sort(
        key=lambda c: (
            c.person.state == "off_shift",
            not c.specialty_match,
            STATE_RANK[c.person.state],
            -(c.equipment_score or 0),
            c.person.queue_count,
            c.person.employee.full_name,
        )
    )
    top = candidates[0] if candidates else None
    if top and top.specialty_match and top.person.state != "off_shift":
        top.recommended = True

    return Assist(
        specialty=specialty,
        fault_code=fault,
        order_type=OrderType.PLANNED if priority == Priority.PLANNED else OrderType.UNPLANNED,
        deadline_hours=default_deadline_hours(priority, fault.norm_hours if fault else None),
        candidates=candidates,
    )
