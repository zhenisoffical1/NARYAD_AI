"""Наполнение базы. Запуск: python -m seed

Сейчас создаёт базовые учётные записи всех ролей; полный генератор истории — следующий шаг.
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Employee
from app.models.enums import Role, Shift
from app.security import hash_pin

BASE_ACCOUNTS = [
    ("admin", "Администратор Системы", Role.ADMIN, "0000", None),
    ("boss", "Жумабеков Нурлан Серикович", Role.BOSS, "1111", None),
    ("master1", "Ковалёв Андрей Петрович", Role.MASTER, "2222", Shift.DAY),
    ("worker1", "Ахметов Ерлан Каиртаевич", Role.WORKER, "3333", Shift.DAY),
]


async def main() -> None:
    async with SessionLocal() as session:
        existing = set(await session.scalars(select(Employee.login)))
        for login, full_name, role, pin, shift in BASE_ACCOUNTS:
            if login in existing:
                continue
            session.add(
                Employee(
                    login=login,
                    full_name=full_name,
                    role=role,
                    pin_hash=hash_pin(pin),
                    shift=shift,
                    on_shift=shift is not None,
                    specialty="слесарь-ремонтник" if role == Role.WORKER else None,
                )
            )
        await session.commit()
    print("Учётные записи созданы: admin/0000, boss/1111, master1/2222, worker1/3333")


if __name__ == "__main__":
    asyncio.run(main())
