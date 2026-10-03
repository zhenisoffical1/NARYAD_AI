"""История нарядов за 3 месяца с заложенными закономерностями (CLAUDE.md, раздел 7).

Всё детерминировано seed=42: при одинаковой дате запуска получается одинаковая база.
Сила каждой закономерности задаётся в PatternConfig — так её можно ослабить и проверить,
что детекторы всё ещё её видят.
"""

import heapq
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AiAssessment, Employee, MaterialWriteoff, Order, OrderEvent
from app.models.enums import (
    AssessmentStatus,
    Criticality,
    OrderStatus,
    OrderType,
    Priority,
    Shift,
)
from app.services.shifts import shift_bounds, shift_of
from app.services.verification.aggregate import aggregate
from app.services.verification.facts import CheckResult, ClosureFacts, MaterialFact
from app.services.verification.llm_check import mock_works_match
from app.services.verification.rules import run_rules
from app.services.verification.texts import master_report, worker_report
from seed.reference_data import (
    CATEGORY_SPECIALTIES,
    LUBRICANT_CATEGORY,
    PPR_FAULT_CODE,
    PPR_WORKS,
    WELDER,
)
from seed.world import World

S = OrderStatus


@dataclass(frozen=True)
class PatternConfig:
    # 1. Конвейер К-3 ломается в N раз чаще среднего, в основном за последние 30 дней, шифр М-02
    k3_inv: str = "КТ-003"
    k3_multiplier: float = 3.0
    k3_recent_share: float = 0.75
    k3_bearing_share: float = 0.85
    # 2. Исполнитель с ~30% возвратов на доработку и повторных поломок ≤7 дней
    returns_login: str = "melnikov"
    returns_rework_rate: float = 0.17
    returns_repeat_rate: float = 0.15
    # 3. Дробилка КМД-1750 ломается в течение N дней после ППР бригады №2
    ppr_inv: str = "ДР-001"
    ppr_brigade: str = "Бригада №2"
    ppr_other_brigade: str = "Бригада №1"
    ppr_breakdown_days: int = 5
    # 4. Обогащение: электрические отказы ночью в N раз чаще, чем днём
    night_section: str = "Обогащение"
    night_ratio: float = 2.5
    # 5. Исполнитель списывает смазочные материалы в N раз выше нормы
    lube_login: str = "seitkaziev"
    lube_overuse: tuple[float, float] = (2.0, 2.45)


@dataclass(frozen=True)
class HistoryConfig:
    seed: int = 42
    days: int = 90
    base_rate: tuple[tuple[Criticality, float], ...] = (
        (Criticality.A, 0.29),
        (Criticality.B, 0.22),
        (Criticality.C, 0.14),
    )
    ppr_interval_days: tuple[tuple[Criticality, int], ...] = (
        (Criticality.A, 14),
        (Criticality.B, 21),
        (Criticality.C, 30),
    )
    electrical_ppr_days: int = 30
    post_ppr_factor: float = 0.3  # после ППР поломок меньше
    post_ppr_window_days: int = 7
    night_share: float = 0.42
    rework_rate: float = 0.025
    repeat_rate: float = 0.03
    reject_rate: float = 0.03
    cancel_rate: float = 0.01
    override_rate: float = 0.03
    patterns: PatternConfig = field(default_factory=PatternConfig)


@dataclass(order=True)
class Plan:
    created_at: datetime
    seq: int
    inv: str = field(compare=False)
    fault: str = field(compare=False)
    priority: Priority = field(compare=False)
    planned: bool = field(compare=False, default=False)
    brigade: str | None = field(compare=False, default=None)
    tag: str = field(compare=False, default="base")
    shift: Shift = field(compare=False, default=Shift.DAY)


@dataclass
class HistoryResult:
    orders: int
    history_end: datetime
    stats: dict[str, int] = field(default_factory=dict)


class Generator:
    def __init__(self, world: World, cfg: HistoryConfig, now: datetime) -> None:
        self.w = world
        self.cfg = cfg
        self.p = cfg.patterns
        self.rng = random.Random(cfg.seed)
        self.tz = settings.tz
        _, shift_start, _ = shift_bounds(now)
        # История заканчивается за 16 ч до текущей смены: всё, что позже, — демо-сцена.
        # Наряды последних суток укорачиваются, чтобы закрыться до начала текущей смены.
        self.history_end = shift_start - timedelta(hours=16)
        self.tail_start = self.history_end - timedelta(hours=30)
        local_end = self.history_end.astimezone(self.tz)
        self.start_day = local_end.date() - timedelta(days=cfg.days)
        self.seq = 0
        self.ppr_log: dict[str, list[tuple[int, str]]] = {}  # inv → [(день, бригада)]
        self.stats: dict[str, int] = {}

    # --- время -----------------------------------------------------------------

    def _moment(self, day: int, shift: Shift, start_h: float = 0, end_h: float = 11.5) -> datetime:
        """Случайный момент внутри смены дня `day` (часы от начала смены)."""
        date = self.start_day + timedelta(days=day)
        base_hour = (
            settings.day_shift_start_hour if shift == Shift.DAY else settings.night_shift_start_hour
        )
        start = datetime.combine(date, time(base_hour), self.tz)
        offset = self.rng.uniform(start_h, end_h) * 60
        return (start + timedelta(minutes=offset)).astimezone(settings.tz)

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def _poisson(self, lam: float) -> int:
        limit, k, prod = math.exp(-lam), 0, self.rng.random()
        while prod > limit:
            k += 1
            prod *= self.rng.random()
        return k

    # --- планы -----------------------------------------------------------------

    def plan_ppr(self) -> list[Plan]:
        plans = []
        intervals = dict(self.cfg.ppr_interval_days)
        for inv, spec in self.w.equipment_specs.items():
            interval = intervals[spec.criticality]
            day = self.rng.randrange(interval)
            index = 0
            while day < self.cfg.days - 1:
                brigade = self._ppr_brigade(inv, spec.section, index)
                self.ppr_log.setdefault(inv, []).append((day, brigade))
                plans.append(
                    Plan(
                        self._moment(day, Shift.DAY, 1, 3),
                        self._next_seq(),
                        inv,
                        PPR_FAULT_CODE,
                        Priority.PLANNED,
                        planned=True,
                        brigade=brigade,
                        tag="ppr",
                    )
                )
                day += interval
                index += 1
            if spec.criticality == Criticality.A:
                eday = self.rng.randrange(self.cfg.electrical_ppr_days)
                while eday < self.cfg.days - 1:
                    plans.append(
                        Plan(
                            self._moment(eday, Shift.DAY, 3, 6),
                            self._next_seq(),
                            inv,
                            "Э-02",
                            Priority.PLANNED,
                            planned=True,
                            brigade="Бригада №3",
                            tag="eppr",
                        )
                    )
                    eday += self.cfg.electrical_ppr_days
        return plans

    def _ppr_brigade(self, inv: str, section: str, index: int) -> str:
        if inv == self.p.ppr_inv:
            return self.p.ppr_brigade if index % 2 == 0 else self.p.ppr_other_brigade
        return {
            "Дробление": "Бригада №1",
            "Обогащение": "Бригада №2",
            "Конвейерный транспорт": "Бригада №1",
            "Ремонтно-механический цех": "Бригада №2",
        }[section]

    def _days_after_ppr(self, inv: str, day: int) -> tuple[int, str] | None:
        """Сколько дней прошло после последнего ППР (если в окне) и какая бригада его делала."""
        best = None
        for ppr_day, brigade in self.ppr_log.get(inv, []):
            if 0 <= day - ppr_day <= self.cfg.post_ppr_window_days:
                best = (day - ppr_day, brigade)
        return best

    def _unplanned_priority(self) -> Priority:
        r = self.rng.random()
        if r < 0.12:
            return Priority.EMERGENCY
        if r < 0.42:
            return Priority.HIGH
        return Priority.NORMAL

    def _shift(self) -> Shift:
        return Shift.NIGHT if self.rng.random() < self.cfg.night_share else Shift.DAY

    def plan_unplanned(self) -> list[Plan]:
        rates = dict(self.cfg.base_rate)
        plans = []
        for inv, spec in self.w.equipment_specs.items():
            last_seen: dict[str, int] = {}  # шифр → день последней поломки
            for day in range(self.cfg.days - 1):
                lam = rates[spec.criticality]
                after = self._days_after_ppr(inv, day)
                if after:
                    if inv == self.p.ppr_inv and after[1] == self.p.ppr_other_brigade:
                        lam = 0.0  # после ППР бригады №1 дробилка работает без отказов
                    else:
                        lam *= self.cfg.post_ppr_factor
                for _ in range(self._poisson(lam)):
                    # Повтор того же шифра за неделю — это сигнал, а не фон: в фоне его нет
                    fresh = [
                        code
                        for code in spec.faults
                        if day - last_seen.get(code, -100) > self.cfg.post_ppr_window_days
                    ]
                    if not fresh:
                        continue
                    code = self.rng.choice(fresh)
                    last_seen[code] = day
                    shift = self._shift()
                    plans.append(
                        Plan(
                            self._moment(day, shift),
                            self._next_seq(),
                            inv,
                            code,
                            self._unplanned_priority(),
                            shift=shift,
                        )
                    )
        return plans

    def plan_ppr_breakdowns(self) -> list[Plan]:
        """Закономерность 3: после ППР бригады №2 дробилка КМД-1750 ломается за 1–5 дней."""
        plans = []
        for day, brigade in self.ppr_log.get(self.p.ppr_inv, []):
            if brigade != self.p.ppr_brigade:
                continue
            last_day = min(day + self.p.ppr_breakdown_days - 1, self.cfg.days - 3)
            if last_day <= day:
                continue
            for _ in range(self.rng.choice((1, 2))):
                bday = self.rng.randint(day + 1, last_day)
                shift = self._shift()
                plans.append(
                    Plan(
                        self._moment(bday, shift),
                        self._next_seq(),
                        self.p.ppr_inv,
                        self.rng.choice(("М-04", "М-06", "Г-02", "М-02")),
                        self.rng.choice((Priority.HIGH, Priority.EMERGENCY)),
                        shift=shift,
                        tag="ppr_breakdown",
                    )
                )
        return plans

    def plan_k3(self, unplanned: list[Plan]) -> list[Plan]:
        """Закономерность 1: К-3 — в N раз больше внеплановых, чем в среднем по оборудованию."""
        counts: dict[str, int] = {inv: 0 for inv in self.w.equipment_specs}
        for plan in unplanned:
            counts[plan.inv] += 1
        others = [c for inv, c in counts.items() if inv != self.p.k3_inv]
        target = round(self.p.k3_multiplier * (sum(others) / len(others)) * 1.1)
        extra = max(0, target - counts[self.p.k3_inv])
        spec = self.w.equipment_specs[self.p.k3_inv]
        plans = []
        for i in range(extra):
            recent = i < round(extra * self.p.k3_recent_share)
            day = (
                self.rng.randint(self.cfg.days - 30, self.cfg.days - 2)
                if recent
                else self.rng.randint(0, self.cfg.days - 31)
            )
            fault = (
                "М-02"
                if self.rng.random() < self.p.k3_bearing_share
                else self.rng.choice(spec.faults)
            )
            shift = self._shift()
            plans.append(
                Plan(
                    self._moment(day, shift),
                    self._next_seq(),
                    self.p.k3_inv,
                    fault,
                    self.rng.choice((Priority.HIGH, Priority.HIGH, Priority.EMERGENCY)),
                    shift=shift,
                    tag="k3",
                )
            )
        return plans

    def apply_night_pattern(self, plans: list[Plan]) -> None:
        """Закономерность 4: электрические отказы на обогащении — ночью в N раз чаще."""
        group = [
            p
            for p in plans
            if not p.planned
            and p.fault.startswith("Э")
            and self.w.equipment_specs[p.inv].section == self.p.night_section
        ]
        self.rng.shuffle(group)
        nights = round(len(group) * self.p.night_ratio / (1 + self.p.night_ratio))
        for i, plan in enumerate(group):
            shift = Shift.NIGHT if i < nights else Shift.DAY
            local = plan.created_at.astimezone(self.tz)
            day = (local.date() - self.start_day).days
            if local.hour < settings.day_shift_start_hour:
                day -= 1  # ночная смена началась накануне
            plan.shift = shift
            plan.created_at = self._moment(max(day, 0), shift)

    # --- исполнение ------------------------------------------------------------

    def _candidates(self, plan: Plan) -> list[Employee]:
        category = self.w.fault_specs[plan.fault].code[0]
        specialties = CATEGORY_SPECIALTIES[category]
        if plan.fault == "М-05":
            specialties = (WELDER,)
        pool = [w for w in self.w.workers if w.specialty in specialties]
        if plan.brigade:
            brigade_id = self.w.brigades[plan.brigade].id
            in_brigade = [w for w in pool if w.brigade_id == brigade_id and w.shift == Shift.DAY]
            pool = in_brigade or [w for w in pool if w.brigade_id == brigade_id] or pool
        else:
            on_shift = [w for w in pool if w.shift == plan.shift]
            pool = on_shift or pool
        return pool

    def _minutes(self, lo: float, hi: float) -> timedelta:
        return timedelta(minutes=self.rng.uniform(lo, hi))

    def _quantity(self, norm: Decimal, unit: str, factor: float) -> Decimal:
        if unit == "шт":
            return Decimal(max(1, round(float(norm) * factor)))
        return (norm * Decimal(str(factor))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    def _writeoffs(self, plan: Plan, worker: Employee) -> list[tuple[str, Decimal]]:
        spec = self.w.fault_specs[plan.fault]
        if plan.tag == "eppr":
            return []
        lines = []
        for name, qty in spec.materials:
            material = self.w.materials[name]
            norm = Decimal(str(qty))
            if worker.login == self.p.lube_login and material.category == LUBRICANT_CATEGORY:
                factor = self.rng.uniform(*self.p.lube_overuse)
            elif self.rng.random() < 0.05:
                factor = self.rng.uniform(1.55, 1.95)  # изредка перерасход и у остальных
            else:
                factor = self.rng.uniform(0.8, 1.2)
            lines.append((name, self._quantity(norm, material.unit, factor)))
        return lines

    def _works(self, plan: Plan, mismatch: bool) -> str:
        if plan.tag == "eppr":
            return "Плановая ревизия электрооборудования: протянуты контакты, замерена изоляция"
        if plan.planned:
            return self.rng.choice(PPR_WORKS)
        if mismatch:
            # Исполнитель устранил не то: работы по другому узлу
            other = self.rng.choice(
                [s for c, s in self.w.fault_specs.items() if c[0] != plan.fault[0]]
            )
            return self.rng.choice(other.works)
        if self.rng.random() < 0.04:
            return "Отремонтировано"
        return self.rng.choice(self.w.fault_specs[plan.fault].works)

    def _facts(
        self,
        order: Order,
        plan: Plan,
        works: str,
        lines: list[tuple[str, Decimal]],
        started: datetime,
        done: datetime,
        paused: int,
    ) -> ClosureFacts:
        spec = self.w.fault_specs[plan.fault]
        norms = {name: Decimal(str(q)) for name, q in spec.materials}
        eq_spec = self.w.equipment_specs[plan.inv]
        return ClosureFacts(
            number=order.number,
            order_type=order.type,
            priority=order.priority,
            equipment=eq_spec.name,
            equipment_type=eq_spec.type,
            description=order.description,
            works_done=works,
            fault_code=spec.code,
            fault_name=spec.name,
            norm_hours=order.norm_hours,
            norm_materials=tuple(
                (name, self.w.materials[name].unit, q) for name, q in norms.items()
            ),
            no_materials=not lines,
            materials=tuple(
                MaterialFact(
                    name=name,
                    unit=self.w.materials[name].unit,
                    quantity=qty,
                    category=self.w.materials[name].category,
                    norm_quantity=norms.get(name),
                )
                for name, qty in lines
            ),
            after_photos=0,
            before_photos=0,
            issued_at=order.issued_at or order.created_at,
            started_at=started,
            done_at=done,
            deadline_at=order.deadline_at,
            paused_minutes=paused,
            archive=True,
        )

    def _assess(self, facts: ClosureFacts, at: datetime) -> AiAssessment:
        checks = run_rules(facts)
        match = mock_works_match(facts)
        checks.append(match.check)
        checks.append(
            CheckResult(
                "photos",
                "Фото до и после",
                "skip",
                "Архивный наряд — фото в систему не загружались.",
            )
        )
        result = aggregate(checks, match.confidence)
        return AiAssessment(
            status=AssessmentStatus.DONE,
            mode="mock",
            verdict=result.verdict,
            score_0_100=result.score,
            confidence=round(result.confidence, 2),
            needs_master_review=result.needs_master_review,
            explanation_worker=worker_report(facts, checks, result),
            explanation_master=master_report(facts, checks, result),
            checks=[c.as_dict() for c in checks],
            created_at=at,
            finished_at=at + timedelta(seconds=self.rng.randint(6, 14)),
        )

    def simulate(self, plan: Plan, number: int) -> tuple[Order, list[AiAssessment], Plan | None]:
        rng = self.rng
        spec = self.w.fault_specs[plan.fault]
        eq = self.w.equipment[plan.inv]
        eq_spec = self.w.equipment_specs[plan.inv]
        master = self.w.masters[shift_of(plan.created_at)]
        candidates = self._candidates(plan)
        worker = rng.choice(candidates)

        created = plan.created_at
        norm = Decimal(str(spec.norm_hours))
        default_hours = {
            Priority.EMERGENCY: settings.deadline_hours_emergency,
            Priority.HIGH: settings.deadline_hours_high,
            Priority.NORMAL: settings.deadline_hours_normal,
            Priority.PLANNED: settings.deadline_hours_planned,
        }[plan.priority]
        deadline = created + timedelta(hours=max(default_hours, float(norm) * 1.25))
        stopped = plan.priority == Priority.EMERGENCY or (
            plan.priority == Priority.HIGH and rng.random() < 0.5
        )
        if plan.planned:
            description = (
                f"ППР по графику: {eq_spec.type.lower()} {eq_spec.name}"
                if plan.tag == "ppr"
                else f"Плановая ревизия электрооборудования: {eq_spec.name}"
            )
        else:
            description = rng.choice(spec.descriptions)

        order = Order(
            number=number,
            type=OrderType.PLANNED if plan.planned else OrderType.UNPLANNED,
            priority=plan.priority,
            status=S.ISSUED,
            description=description,
            section_id=eq.section_id,
            equipment_id=eq.id,
            assignee_id=worker.id,
            brigade_id=self.w.brigades[plan.brigade].id if plan.brigade else worker.brigade_id,
            master_id=master.id,
            deadline_at=deadline,
            norm_hours=norm,
            equipment_stopped=stopped and not plan.planned,
            created_at=created,
            issued_at=created,
        )
        events: list[OrderEvent] = []

        def event(
            action: str,
            to: S | None,
            at: datetime,
            actor: Employee | None,
            reason: str | None = None,
            comment: str | None = None,
            data: dict[str, object] | None = None,
        ) -> None:
            events.append(
                OrderEvent(
                    action=action,
                    from_status=order.status if to else None,
                    to_status=to,
                    actor_id=actor.id if actor else None,
                    reason=reason,
                    comment=comment,
                    data=data,
                    created_at=at,
                )
            )
            if to is not None:
                order.status = to
                field_name = {
                    S.ISSUED: "issued_at",
                    S.QUEUED: "queued_at",
                    S.ACCEPTED: "accepted_at",
                    S.REJECTED: "rejected_at",
                    S.IN_PROGRESS: "started_at",
                    S.PAUSED: "paused_at",
                    S.DONE: "done_at",
                    S.AI_REVIEW: "review_at",
                    S.REWORK: "rework_at",
                    S.CLOSED: "closed_at",
                    S.CANCELLED: "cancelled_at",
                }[to]
                setattr(order, field_name, at)

        events.append(
            OrderEvent(
                action="create",
                to_status=S.ISSUED,
                actor_id=master.id,
                data={"priority": plan.priority.value},
                created_at=created,
            )
        )
        t = created

        # Отказ и переназначение
        if (
            not plan.planned
            and plan.priority != Priority.EMERGENCY
            and rng.random() < self.cfg.reject_rate
        ):
            t += self._minutes(2, 8)
            reason = rng.choice(("занят аварийным", "нет допуска", "нет материалов"))
            event("reject", S.REJECTED, t, worker, reason=reason)
            others = [c for c in candidates if c.id != worker.id] or candidates
            worker = rng.choice(others)
            order.assignee_id = worker.id
            t += self._minutes(3, 12)
            event("reissue", S.ISSUED, t, master, data={"to_assignee_id": worker.id})

        # Отмена
        if rng.random() < self.cfg.cancel_rate:
            t += self._minutes(5, 40)
            event(
                "cancel",
                S.CANCELLED,
                t,
                master,
                reason="Дубль заявки — работы выполнены по другому наряду",
            )
            order.events = events
            return order, [], None

        # Принятие (иногда через очередь)
        if (
            plan.priority in (Priority.NORMAL, Priority.PLANNED)
            and rng.random() < 0.3
            and not (created >= self.tail_start)
        ):
            t += self._minutes(1, 10)
            event("queue", S.QUEUED, t, worker)
            t += self._minutes(20, 150)
        else:
            delay = {
                Priority.EMERGENCY: (1, 4),
                Priority.HIGH: (2, 12),
                Priority.NORMAL: (3, 30),
                Priority.PLANNED: (10, 90),
            }[plan.priority]
            t += self._minutes(*delay)
        event("accept", S.ACCEPTED, t, worker)
        t += self._minutes(1, 6) if plan.priority == Priority.EMERGENCY else self._minutes(2, 20)
        event("start", S.IN_PROGRESS, t, worker)
        started = t

        tail = created >= self.tail_start
        factor = min(1.2 if tail else 2.8, max(0.35, rng.lognormvariate(0, 0.28)))
        if worker.login == self.p.returns_login:
            factor *= 1.1
        work = timedelta(minutes=float(norm) * 60 * factor)
        paused = 0
        if not tail and rng.random() < 0.1:
            t += work * rng.uniform(0.2, 0.6)
            reason = rng.choice(("ждёт запчасти", "ждёт остановки оборудования"))
            event("pause", S.PAUSED, t, worker, reason=reason)
            paused = rng.randint(30, 150)
            t += timedelta(minutes=paused)
            event("resume", S.IN_PROGRESS, t, worker)
            t += work * rng.uniform(0.4, 0.8)
        else:
            t += work

        # Качество: возвраты на доработку и повторные поломки
        is_returns_worker = worker.login == self.p.returns_login
        rework_rate = self.p.returns_rework_rate if is_returns_worker else self.cfg.rework_rate
        repeat_rate = self.p.returns_repeat_rate if is_returns_worker else self.cfg.repeat_rate
        roll = rng.random()
        rework = not plan.planned and roll < rework_rate
        repeat = not plan.planned and rework_rate <= roll < rework_rate + repeat_rate

        lines = self._writeoffs(plan, worker)
        works = self._works(plan, mismatch=rework)
        assessments = []

        def complete(at: datetime, works_text: str) -> AiAssessment:
            order.works_done = works_text
            order.fault_code_id = self.w.faults[plan.fault].id
            order.no_materials = not lines
            event("complete", S.DONE, at, worker)
            event("begin_review", S.AI_REVIEW, at, None)
            facts = self._facts(order, plan, works_text, lines, started, at, paused)
            assessment = self._assess(facts, at)
            assessments.append(assessment)
            return assessment

        first = complete(t, works)
        if first.verdict == "rework":
            t += timedelta(seconds=15)
            event("send_to_rework", S.REWORK, t, None, reason="Вердикт ИИ: требует доработки")
            t += self._minutes(10, 60)
            event("resume_rework", S.IN_PROGRESS, t, worker)
            t += self._minutes(20, 90)
            complete(t, self.rng.choice(spec.works))

        final = assessments[-1]
        if final.verdict == "rework":
            # Мастер разобрался на месте и закрыл с правкой оценки
            final.master_override_score = 65
            final.master_comment = "Проверил на месте: работа выполнена, замечание учтено."
            final.master_id = master.id
        elif rng.random() < self.cfg.override_rate and final.score_0_100 is not None:
            delta = rng.choice((-10, -5, 5, 10))
            final.master_override_score = max(0, min(100, final.score_0_100 + delta))
            final.master_comment = (
                "Проверил на месте — качество выше оценки ИИ."
                if delta > 0
                else "На месте видны недочёты: не убран мусор у узла."
            )
            final.master_id = master.id

        t += self._minutes(10, 120)
        event("close", S.CLOSED, t, master)

        if order.equipment_stopped and order.done_at:
            order.downtime_minutes = int((order.done_at - created).total_seconds() // 60)

        order.events = events
        order.writeoffs = [
            MaterialWriteoff(
                material_id=self.w.materials[name].id,
                quantity=qty,
                unit=self.w.materials[name].unit,
            )
            for name, qty in lines
        ]

        follow_up = None
        # На дробилке КМД-1750 повторы не добавляем — там своя закономерность про ППР
        if repeat and order.done_at and plan.inv != self.p.ppr_inv:
            when = order.done_at + timedelta(days=rng.uniform(2, 7))
            if when < self.history_end - timedelta(hours=1):
                follow_up = Plan(
                    when,
                    self._next_seq(),
                    plan.inv,
                    plan.fault,
                    Priority.HIGH,
                    shift=shift_of(when),
                    tag="repeat",
                )
        return order, assessments, follow_up

    def run(self) -> list[tuple[Order, list[AiAssessment]]]:
        ppr = self.plan_ppr()
        unplanned = self.plan_unplanned()
        unplanned += self.plan_ppr_breakdowns()
        unplanned += self.plan_k3(unplanned)
        self.apply_night_pattern(unplanned)

        limit = self.history_end - timedelta(hours=1)
        queue = [p for p in ppr + unplanned if p.created_at < limit]
        heapq.heapify(queue)
        result = []
        number = 0
        while queue:
            plan = heapq.heappop(queue)
            number += 1
            order, assessments, follow_up = self.simulate(plan, number)
            result.append((order, assessments))
            self.stats[plan.tag] = self.stats.get(plan.tag, 0) + 1
            if follow_up is not None:
                heapq.heappush(queue, follow_up)
        return result


async def generate_history(
    session: AsyncSession, world: World, now: datetime, cfg: HistoryConfig | None = None
) -> HistoryResult:
    generator = Generator(world, cfg or HistoryConfig(), now)
    produced = generator.run()

    session.add_all(order for order, _ in produced)
    await session.flush()
    for order, assessments in produced:
        for assessment in assessments:
            assessment.order_id = order.id
        session.add_all(assessments)
    await session.flush()
    return HistoryResult(
        orders=len(produced), history_end=generator.history_end, stats=generator.stats
    )
