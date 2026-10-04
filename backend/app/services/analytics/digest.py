"""Еженедельная сводка руководителю и мастерам: главное из аналитики за 30 дней."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee
from app.models.enums import Role
from app.services.analytics import Scope, run_detectors
from app.services.analytics.insights import explain
from app.services.notifications.notify import notify

TOP = 3


async def weekly_digest(session: AsyncSession) -> int:
    """Отправить сводку; возвращает число получателей. Commit — у вызывающего."""
    findings = [f for f in await run_detectors(session, Scope(days=30)) if f.severity != "info"]
    if findings:
        items = await explain(findings[:TOP])
        lines = [f"{n}. {i.conclusion} {i.recommendation}" for n, i in enumerate(items, 1)]
        body = "\n".join(lines)
        if len(findings) > TOP:
            body += f"\nВсего находок: {len(findings)} — подробности в разделе «Аналитика»."
    else:
        body = "За 30 дней закономерностей, требующих внимания, не найдено."

    recipients = list(
        await session.scalars(
            select(Employee.id).where(
                Employee.role.in_([Role.BOSS, Role.MASTER]), Employee.is_active.is_(True)
            )
        )
    )
    for employee_id in recipients:
        await notify(
            session,
            employee_id=employee_id,
            kind="weekly_digest",
            title="Сводка аналитики за неделю",
            body=body,
        )
    return len(recipients)
