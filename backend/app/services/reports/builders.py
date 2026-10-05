"""Сборка отчётов (ТЗ, раздел 7): по нарядам за период, по наряду, рейтинг, материалы, простои."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import NotFound
from app.models import (
    AiAssessment,
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    MaterialWriteoff,
    Order,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.base import utcnow
from app.models.enums import (
    DEADLINE_TRACKED_STATUSES,
    PRIORITY_LABELS,
    STATUS_LABELS,
    OrderStatus,
    OrderType,
)
from app.services.analytics.detectors import num
from app.services.llm import ask_json, facts_json, prompt, text_block
from app.services.orders import latest_assessments
from app.services.quality import had_rework
from app.services.rating import compute_ratings
from app.services.reports.model import Column, Kpi, Report, Table, Window, fmt_dt
from app.services.verification.texts import VERDICT_LABELS

S = OrderStatus
DONE = {S.DONE, S.AI_REVIEW, S.CLOSED}
MATERIAL_WARN = 1.5


@dataclass(frozen=True, slots=True)
class ReportFilter:
    """Срез отчёта: участок, оборудование, исполнитель, бригада (любые вместе)."""

    section_id: int | None = None
    equipment_id: int | None = None
    employee_id: int | None = None
    brigade_id: int | None = None


def _where(stmt: Select[Any], f: ReportFilter) -> Select[Any]:
    if f.section_id is not None:
        stmt = stmt.where(Order.section_id == f.section_id)
    if f.equipment_id is not None:
        stmt = stmt.where(Order.equipment_id == f.equipment_id)
    if f.employee_id is not None:
        stmt = stmt.where(Order.assignee_id == f.employee_id)
    if f.brigade_id is not None:
        members = select(Employee.id).where(Employee.brigade_id == f.brigade_id)
        stmt = stmt.where(or_(Order.brigade_id == f.brigade_id, Order.assignee_id.in_(members)))
    return stmt


async def _orders(session: AsyncSession, w: Window, f: ReportFilter) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.created_at >= w.start, Order.created_at < w.end)
        .options(
            selectinload(Order.equipment),
            selectinload(Order.section),
            selectinload(Order.assignee),
            selectinload(Order.fault_code),
            selectinload(Order.events),
        )
        .order_by(Order.number)
    )
    return list(await session.scalars(_where(stmt, f)))


async def _filters(session: AsyncSession, f: ReportFilter) -> str | None:
    parts: list[str] = []
    if f.section_id is not None and (section := await session.get(Section, f.section_id)):
        parts.append(f"Участок: {section.name}")
    if f.equipment_id is not None and (eq := await session.get(Equipment, f.equipment_id)):
        parts.append(f"Оборудование: {eq.inv_number} {eq.name}")
    if f.employee_id is not None and (person := await session.get(Employee, f.employee_id)):
        parts.append(f"Исполнитель: {person.short_name}")
    if f.brigade_id is not None and (brigade := await session.get(Brigade, f.brigade_id)):
        parts.append(f"Бригада: {brigade.name}")
    return "; ".join(parts) or None


def _overdue(o: Order) -> bool:
    finished = o.done_at or (utcnow() if o.status in DEADLINE_TRACKED_STATUSES else None)
    return finished is not None and finished > o.deadline_at


def hours(minutes: int) -> str:
    return f"{num(minutes / 60)} ч"


# --- 1. Наряды за период (смена / сутки / неделя / месяц) -----------------------------------


class _Summary(BaseModel):
    summary: str = Field(max_length=1500)


def _template_summary(data: dict[str, Any]) -> str:
    text = (
        f"Выдано нарядов: {data['выдано']}, исполнено: {data['исполнено']}, "
        f"закрыто мастером: {data['закрыто']}."
    )
    if data["просрочено"]:
        text += f" Просрочено: {data['просрочено']}."
    if data["отклонено"]:
        text += f" Отклонено исполнителями: {data['отклонено']}."
    if data["возвраты"]:
        text += f" Возвращено на доработку: {data['возвраты']}."
    if data["простой_ч"]:
        text += f" Простой оборудования — {num(data['простой_ч'])} ч"
        if data["больше_всего_простоя"]:
            text += f", больше всего — {data['больше_всего_простоя']}"
        text += "."
    if data["средняя_оценка_ии"] is not None:
        text += f" Средняя оценка ИИ-проверки — {data['средняя_оценка_ии']} из 100."
    if data["в_работе_на_конец"]:
        text += f" Переходит на следующую смену: {data['в_работе_на_конец']} нарядов в работе."
    return text


async def orders_report(session: AsyncSession, w: Window, f: ReportFilter) -> Report:
    orders = await _orders(session, w, f)
    assessments = await latest_assessments(session, [o.id for o in orders])

    done = [o for o in orders if o.status in DONE]
    closed = [o for o in orders if o.status == S.CLOSED]
    overdue = [o for o in orders if _overdue(o)]
    rework = [o for o in orders if had_rework(o)]
    rejected = [o for o in orders if any(e.to_status == S.REJECTED for e in o.events)]
    active = [o for o in orders if o.status in DEADLINE_TRACKED_STATUSES]
    downtime: dict[str, int] = defaultdict(int)
    for o in orders:
        if o.downtime_minutes:
            downtime[o.equipment.name] += o.downtime_minutes
    total_downtime = sum(downtime.values())
    scores = [a.final_score for a in assessments.values() if a.final_score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    rows = []
    for o in orders:
        a = assessments.get(o.id)
        rows.append(
            {
                "number": o.number,
                "created": fmt_dt(o.created_at),
                "equipment": o.equipment.name,
                "priority": PRIORITY_LABELS[o.priority],
                "assignee": o.assignee.short_name if o.assignee else "—",
                "status": STATUS_LABELS[o.status],
                "deadline": fmt_dt(o.deadline_at),
                "done": fmt_dt(o.done_at),
                "score": a.final_score if a and a.final_score is not None else "—",
                "overdue": "да" if _overdue(o) else "",
            }
        )

    by_worker: dict[str, dict[str, Any]] = {}
    for o in orders:
        if o.assignee is None:
            continue
        stat = by_worker.setdefault(
            o.assignee.short_name,
            {"worker": o.assignee.short_name, "issued": 0, "done": 0, "overdue": 0, "scores": []},
        )
        stat["issued"] += 1
        stat["done"] += o.status in DONE
        stat["overdue"] += _overdue(o)
        a = assessments.get(o.id)
        if a and a.final_score is not None:
            stat["scores"].append(a.final_score)
    worker_rows = [
        {
            **{k: v for k, v in s.items() if k != "scores"},
            "score": round(sum(s["scores"]) / len(s["scores"])) if s["scores"] else "—",
        }
        for s in sorted(by_worker.values(), key=lambda s: -s["issued"])
    ]

    data = {
        "период": w.label,
        "выдано": len(orders),
        "исполнено": len(done),
        "закрыто": len(closed),
        "просрочено": len(overdue),
        "возвраты": len(rework),
        "отклонено": len(rejected),
        "простой_ч": round(total_downtime / 60, 1),
        "больше_всего_простоя": max(downtime, key=downtime.__getitem__) if downtime else None,
        "средняя_оценка_ии": avg_score,
        "в_работе_на_конец": len(active),
        "просроченные_наряды": [f"№{o.number} {o.equipment.name}" for o in overdue[:5]],
    }
    llm = await ask_json(
        "shift_summary",
        _Summary,
        system=prompt("shift_summary"),
        content=[text_block(facts_json(data))],
        fast=True,
    )

    return Report(
        kind="orders",
        title="Отчёт по нарядам",
        period_label=w.label,
        generated_at=utcnow(),
        filters=await _filters(session, f),
        kpis=[
            Kpi("Выдано", str(len(orders))),
            Kpi("Исполнено", str(len(done)), "ok"),
            Kpi("Просрочено", str(len(overdue)), "danger" if overdue else "default"),
            Kpi("Отклонено", str(len(rejected)), "danger" if rejected else "default"),
            Kpi("На доработку", str(len(rework)), "danger" if rework else "default"),
            Kpi("Простой", hours(total_downtime), "danger" if total_downtime else "default"),
            Kpi("Средняя оценка ИИ", str(avg_score) if avg_score is not None else "—"),
        ],
        summary=llm.summary if llm else _template_summary(data),
        summary_source="llm" if llm else "rules",
        tables=[
            Table(
                "Наряды",
                [
                    Column("number", "№", "right", 7),
                    Column("created", "Выдан", width=12),
                    Column("equipment", "Оборудование", width=32),
                    Column("priority", "Приоритет", width=11),
                    Column("assignee", "Исполнитель", width=16),
                    Column("status", "Статус", width=15),
                    Column("deadline", "Срок", width=12),
                    Column("done", "Исполнен", width=12),
                    Column("score", "Оценка ИИ", "right", 10),
                    Column("overdue", "Просрочен", width=10),
                ],
                rows,
                highlight="overdue",
            ),
            Table(
                "По исполнителям",
                [
                    Column("worker", "Исполнитель", width=18),
                    Column("issued", "Выдано", "right", 9),
                    Column("done", "Исполнено", "right", 10),
                    Column("overdue", "Просрочено", "right", 11),
                    Column("score", "Средняя оценка", "right", 14),
                ],
                worker_rows,
            ),
        ],
    )


# --- 2. Отчёт по наряду -------------------------------------------------------------------


async def order_report(session: AsyncSession, order_id: int) -> Report:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.equipment),
            selectinload(Order.section),
            selectinload(Order.assignee),
            selectinload(Order.master),
            selectinload(Order.fault_code),
            selectinload(Order.events),
            selectinload(Order.writeoffs).selectinload(MaterialWriteoff.material),
        )
    )
    if order is None:
        raise NotFound("Наряд не найден.")
    assessment = await session.scalar(
        select(AiAssessment)
        .where(AiAssessment.order_id == order_id)
        .order_by(AiAssessment.id.desc())
        .limit(1)
    )
    equipment = f"{order.equipment.name} ({order.equipment.inv_number})"
    facts = [
        {"field": "Оборудование", "value": equipment},
        {"field": "Участок", "value": order.section.name},
        {"field": "Тип", "value": "Плановый" if order.type == OrderType.PLANNED else "Внеплановый"},
        {"field": "Приоритет", "value": PRIORITY_LABELS[order.priority]},
        {"field": "Проблема", "value": order.description},
        {"field": "Мастер", "value": order.master.short_name},
        {"field": "Исполнитель", "value": order.assignee.short_name if order.assignee else "—"},
        {"field": "Срок", "value": fmt_dt(order.deadline_at)},
        {"field": "Статус", "value": STATUS_LABELS[order.status]},
    ]
    if order.fault_code:
        facts.append(
            {"field": "Шифр", "value": f"{order.fault_code.code} — {order.fault_code.name}"}
        )
    if order.works_done:
        facts.append({"field": "Что сделано", "value": order.works_done})
    if order.downtime_minutes:
        facts.append({"field": "Простой", "value": hours(order.downtime_minutes)})

    events = [
        {
            "at": fmt_dt(e.created_at),
            "what": STATUS_LABELS[e.to_status] if e.to_status else e.action,
            "comment": e.reason or e.comment or "",
        }
        for e in order.events
    ]
    materials = [
        {"material": w.material.name, "qty": f"{num(float(w.quantity), 3)} {w.unit}"}
        for w in order.writeoffs
    ]

    kpis = []
    summary = None
    if assessment and assessment.score_0_100 is not None:
        verdict = (
            VERDICT_LABELS[assessment.verdict] if assessment.verdict else "на решении мастера"
        ).capitalize()
        kpis = [
            Kpi("Оценка ИИ", f"{assessment.final_score} из 100"),
            Kpi("Вердикт", verdict, "danger" if assessment.verdict == "rework" else "ok"),
        ]
        if assessment.score_1_5:
            kpis.append(Kpi("Оценка по фото", f"{assessment.score_1_5} из 5"))
        summary = assessment.explanation_master
        if assessment.master_comment:
            summary = (summary or "") + f"\n\nКомментарий мастера: {assessment.master_comment}"

    tables = [
        Table("Наряд", [Column("field", "", width=18), Column("value", "", width=70)], facts),
        Table(
            "Ход работ",
            [
                Column("at", "Когда", width=12),
                Column("what", "Событие", width=24),
                Column("comment", "Комментарий", width=50),
            ],
            events,
        ),
    ]
    if materials:
        tables.append(
            Table(
                "Материалы",
                [Column("material", "Материал", width=40), Column("qty", "Количество", width=14)],
                materials,
            )
        )
    return Report(
        kind="order",
        title=f"Наряд №{order.number}",
        period_label=f"Выдан {fmt_dt(order.created_at)}",
        generated_at=utcnow(),
        kpis=kpis,
        summary=summary,
        summary_source="rules" if summary else None,
        tables=tables,
    )


# --- 3. Рейтинг ---------------------------------------------------------------------------


async def rating_report(session: AsyncSession, w: Window) -> Report:
    report = await compute_ratings(session, days=w.days, now=w.end)
    workers = [
        {
            "rank": r.rank or "—",
            "worker": r.employee.full_name,
            "orders": r.orders,
            "score": num(r.score) if r.score is not None else "мало данных",
            **{c.key: num(c.points) for c in r.components},
        }
        for r in report.workers
    ]
    brigades = [
        {
            "brigade": b.brigade.name,
            "members": b.members,
            "orders": b.orders,
            "score": num(b.score) if b.score is not None else "—",
        }
        for b in report.brigades
    ]
    component_columns = [
        Column(c.key, f"{c.label} ({round(c.weight * 100)})", "right", 14)
        for c in (report.workers[0].components if report.workers else [])
    ]
    return Report(
        kind="rating",
        title="Рейтинг исполнителей",
        period_label=w.label,
        generated_at=utcnow(),
        summary=(
            "Рейтинг из 100: качество 35, в срок 25, без возвратов 20, объём с учётом "
            "сложности 15, без отказов без причины 5. Нужно не меньше 5 закрытых нарядов."
        ),
        summary_source="rules",
        tables=[
            Table(
                "Исполнители",
                [
                    Column("rank", "Место", "right", 7),
                    Column("worker", "Исполнитель", width=30),
                    Column("orders", "Нарядов", "right", 9),
                    Column("score", "Рейтинг", "right", 10),
                    *component_columns,
                ],
                workers,
            ),
            Table(
                "Бригады",
                [
                    Column("brigade", "Бригада", width=16),
                    Column("members", "Человек", "right", 9),
                    Column("orders", "Нарядов", "right", 9),
                    Column("score", "Рейтинг", "right", 10),
                ],
                brigades,
            ),
        ],
    )


# --- 4. Материалы с отклонениями от нормы ---------------------------------------------------


async def materials_report(session: AsyncSession, w: Window, f: ReportFilter) -> Report:
    stmt = (
        select(Order)
        .where(Order.done_at >= w.start, Order.done_at < w.end, Order.fault_code_id.is_not(None))
        .options(
            selectinload(Order.equipment),
            selectinload(Order.assignee),
            selectinload(Order.writeoffs).selectinload(MaterialWriteoff.material),
            selectinload(Order.fault_code)
            .selectinload(FaultCode.norm)
            .selectinload(TimeNorm.materials)
            .selectinload(TimeNormMaterial.material),
        )
    )
    orders = list(await session.scalars(_where(stmt, f)))

    rows: list[dict[str, Any]] = []
    totals: dict[str, dict[str, Any]] = {}
    for o in orders:
        assert o.fault_code is not None
        norm = (
            {m.material_id: m.quantity for m in o.fault_code.norm.materials}
            if o.fault_code.norm
            else {}
        )
        for wo in o.writeoffs:
            total = totals.setdefault(
                wo.material.name,
                {
                    "material": wo.material.name,
                    "unit": wo.unit,
                    "fact": Decimal(0),
                    "norm": Decimal(0),
                },
            )
            total["fact"] += wo.quantity
            norm_qty = norm.get(wo.material_id)
            if norm_qty:
                total["norm"] += norm_qty
                ratio = float(wo.quantity / norm_qty)
                if ratio > MATERIAL_WARN:
                    rows.append(
                        {
                            "number": o.number,
                            "done": fmt_dt(o.done_at),
                            "worker": o.assignee.short_name if o.assignee else "—",
                            "code": o.fault_code.code,
                            "material": wo.material.name,
                            "fact": f"{num(float(wo.quantity), 3)} {wo.unit}",
                            "norm": f"{num(float(norm_qty), 3)} {wo.unit}",
                            "ratio": f"×{num(ratio)}",
                            "over": "да" if ratio > 2.5 else "",
                        }
                    )
    rows.sort(key=lambda r: -float(r["ratio"][1:].replace(",", ".")))
    summary_rows = [
        {
            "material": t["material"],
            "fact": f"{num(float(t['fact']), 2)} {t['unit']}",
            "norm": f"{num(float(t['norm']), 2)} {t['unit']}" if t["norm"] else "—",
            "deviation": f"{round((float(t['fact']) / float(t['norm']) - 1) * 100):+d}%"
            if t["norm"]
            else "—",
        }
        for t in sorted(totals.values(), key=lambda t: -float(t["fact"]))
    ]
    return Report(
        kind="materials",
        title="Материалы: расход и отклонения от нормы",
        period_label=w.label,
        generated_at=utcnow(),
        filters=await _filters(session, f),
        kpis=[
            Kpi("Нарядов с материалами", str(sum(1 for o in orders if o.writeoffs))),
            Kpi("Списаний выше нормы ×1,5", str(len(rows)), "danger" if rows else "ok"),
            Kpi("Выше ×2,5", str(sum(1 for r in rows if r["over"])), "danger"),
        ],
        tables=[
            Table(
                "Списания выше нормы",
                [
                    Column("number", "Наряд", "right", 8),
                    Column("done", "Исполнен", width=12),
                    Column("worker", "Исполнитель", width=16),
                    Column("code", "Шифр", width=7),
                    Column("material", "Материал", width=32),
                    Column("fact", "Факт", "right", 10),
                    Column("norm", "Норма", "right", 10),
                    Column("ratio", "К норме", "right", 9),
                ],
                rows,
                note="Норма — расход по нормативу шифра неисправности на один наряд.",
                highlight="over",
            ),
            Table(
                "Итого по материалам",
                [
                    Column("material", "Материал", width=34),
                    Column("fact", "Списано", "right", 12),
                    Column("norm", "По норме", "right", 12),
                    Column("deviation", "Отклонение", "right", 11),
                ],
                summary_rows,
            ),
        ],
    )


# --- 5. Простои по оборудованию и шифрам -------------------------------------------------


async def downtime_report(session: AsyncSession, w: Window, f: ReportFilter) -> Report:
    orders = [o for o in await _orders(session, w, f) if o.downtime_minutes]
    by_equipment: dict[str, dict[str, Any]] = {}
    by_code: dict[str, dict[str, Any]] = {}
    for o in orders:
        minutes = o.downtime_minutes or 0
        e = by_equipment.setdefault(
            o.equipment.name,
            {"equipment": o.equipment.name, "section": o.section.name, "cases": 0, "minutes": 0},
        )
        e["cases"] += 1
        e["minutes"] += minutes
        code = f"{o.fault_code.code} — {o.fault_code.name}" if o.fault_code else "без шифра"
        c = by_code.setdefault(code, {"code": code, "cases": 0, "minutes": 0})
        c["cases"] += 1
        c["minutes"] += minutes
    total = sum(e["minutes"] for e in by_equipment.values())

    def rows(groups: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **g,
                "hours": num(g["minutes"] / 60),
                "share": f"{round(100 * g['minutes'] / total)}%" if total else "—",
            }
            for g in sorted(groups.values(), key=lambda g: -g["minutes"])
        ]

    top = max(by_equipment.values(), key=lambda e: e["minutes"]) if by_equipment else None
    return Report(
        kind="downtime",
        title="Простои оборудования",
        period_label=w.label,
        generated_at=utcnow(),
        filters=await _filters(session, f),
        kpis=[
            Kpi("Простой всего", hours(total), "danger" if total else "ok"),
            Kpi("Случаев", str(len(orders))),
            Kpi("Больше всего", top["equipment"] if top else "—"),
        ],
        tables=[
            Table(
                "По оборудованию",
                [
                    Column("equipment", "Оборудование", width=34),
                    Column("section", "Участок", width=20),
                    Column("cases", "Случаев", "right", 9),
                    Column("hours", "Часов", "right", 9),
                    Column("share", "Доля", "right", 8),
                ],
                rows(by_equipment),
            ),
            Table(
                "По шифрам неисправностей",
                [
                    Column("code", "Шифр", width=48),
                    Column("cases", "Случаев", "right", 9),
                    Column("hours", "Часов", "right", 9),
                    Column("share", "Доля", "right", 8),
                ],
                rows(by_code),
            ),
        ],
    )
