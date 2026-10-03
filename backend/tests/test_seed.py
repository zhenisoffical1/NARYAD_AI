"""Генератор данных: объём из ТЗ, все пять закономерностей, быстрый сброс демо-сцены."""

import time
from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Equipment, FaultCode, Material, Order, Section
from app.models.base import utcnow
from app.models.enums import OrderStatus, Role
from seed.check import collect
from seed.demo import build_scene, set_history_end
from seed.history import HistoryConfig, PatternConfig, generate_history
from seed.world import build_world


async def _seed(session: AsyncSession, cfg: HistoryConfig | None = None) -> int:
    now = utcnow()
    world = await build_world(session)
    history = await generate_history(session, world, now, cfg)
    await set_history_end(session, history.history_end)
    await build_scene(session, now)
    await session.commit()
    return history.orders


async def _count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_volume_matches_spec(session: AsyncSession) -> None:
    orders = await _seed(session)
    assert orders >= 500
    assert await _count(session, Section) == 4
    assert await _count(session, Equipment) == 25
    assert await _count(session, FaultCode) == 20
    assert await _count(session, Material) == 40
    workers = await session.scalar(
        select(func.count()).select_from(Employee).where(Employee.role == Role.WORKER)
    )
    masters = await session.scalar(
        select(func.count()).select_from(Employee).where(Employee.role == Role.MASTER)
    )
    assert (workers, masters) == (15, 2)


async def test_all_patterns_present(session: AsyncSession) -> None:
    await _seed(session)
    report = await collect(session)
    failed = [f"{p.name}: {p.summary}" for p in report.patterns if not p.passed]
    assert not failed, failed


async def test_weakened_pattern_is_detected_as_missing(session: AsyncSession) -> None:
    """Проверка не «всегда зелёная»: без закономерности К-3 она это замечает."""
    weak = HistoryConfig(patterns=replace(PatternConfig(), k3_multiplier=1.0))
    await _seed(session, weak)
    report = await collect(session)
    k3 = report.patterns[0]
    assert not k3.passed
    assert k3.numbers["ratio"] < 2


async def test_scene_reset_is_fast_and_repeatable(session: AsyncSession) -> None:
    await _seed(session)
    history = await session.scalar(
        select(func.count()).select_from(Order).where(Order.status == OrderStatus.CLOSED)
    )

    started = time.perf_counter()
    scene = await build_scene(session)
    await session.commit()
    assert time.perf_counter() - started < 2  # требование: сброс за 2 секунды

    again = await build_scene(session)
    await session.commit()
    assert scene == again == 9
    in_progress = await session.scalar(
        select(func.count()).select_from(Order).where(Order.status == OrderStatus.IN_PROGRESS)
    )
    assert in_progress == 2  # электрик и сварщик в работе — сцена не задвоилась
    closed_now = await session.scalar(
        select(func.count()).select_from(Order).where(Order.status == OrderStatus.CLOSED)
    )
    assert closed_now == history  # история не тронута


@pytest.mark.parametrize("login", ["akhmetov", "kovalchuk"])
async def test_scene_has_two_free_fitters(session: AsyncSession, login: str) -> None:
    from app.services.people import shift_people

    await _seed(session)
    people = {p.employee.full_name.split()[0]: p for p in await shift_people(session)}
    surname = {"akhmetov": "Ахметов", "kovalchuk": "Ковальчук"}[login]
    assert people[surname].state == "free"
    assert people["Абенов"].state == "busy"
    assert people["Байжанов"].state == "queue"
    assert people["Байжанов"].queue_count == 2
    assert people["Нурпеисов"].state == "off_shift"
