"""Тесты идут на SQLite в памяти; в CI — на PostgreSQL (TEST_DATABASE_URL)."""

import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-32b")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["DEMO_MODE"] = "false"  # локальный .env не должен влиять на тесты

from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, engine
from app.main import app
from app.models import Base, Employee, Equipment, Order, Section
from app.models.base import utcnow
from app.models.enums import (
    Criticality,
    OrderStatus,
    OrderType,
    Priority,
    Role,
    Shift,
)
from app.security import create_access_token, hash_pin, login_throttle


@pytest.fixture(autouse=True)
async def _schema() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    login_throttle.reset()
    yield


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


EmployeeFactory = Callable[..., Coroutine[Any, Any, Employee]]


@pytest.fixture
def make_employee(session: AsyncSession) -> EmployeeFactory:
    counter = {"n": 0}

    async def factory(
        role: Role = Role.WORKER, pin: str = "1234", login: str | None = None, **kwargs: Any
    ) -> Employee:
        counter["n"] += 1
        user = Employee(
            login=login or f"{role.value}{counter['n']}",
            full_name=kwargs.pop("full_name", f"Тестов Тест {counter['n']}"),
            role=role,
            pin_hash=hash_pin(pin),
            shift=Shift.DAY,
            on_shift=True,
            **kwargs,
        )
        session.add(user)
        await session.commit()
        return user

    return factory


@pytest.fixture
async def order_factory(
    session: AsyncSession,
) -> Callable[..., Coroutine[Any, Any, Order]]:
    section = Section(name="Дробление")
    session.add(section)
    await session.flush()
    equipment = Equipment(
        name="Дробилка КМД-1750",
        inv_number="ДР-001",
        section_id=section.id,
        type="Дробилка",
        criticality=Criticality.A,
    )
    session.add(equipment)
    await session.commit()
    counter = {"n": 100}

    async def factory(
        *, master: Employee, assignee: Employee | None, status: OrderStatus = OrderStatus.ISSUED
    ) -> Order:
        counter["n"] += 1
        now = utcnow()
        order = Order(
            number=counter["n"],
            type=OrderType.UNPLANNED,
            priority=Priority.HIGH,
            status=status,
            description="Течь масла на редукторе",
            section_id=section.id,
            equipment_id=equipment.id,
            master_id=master.id,
            assignee_id=assignee.id if assignee else None,
            deadline_at=now + timedelta(hours=2),
            norm_hours=Decimal("1.5"),
            issued_at=now,
        )
        session.add(order)
        await session.commit()
        return order

    return factory


def auth_header(user: Employee) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
