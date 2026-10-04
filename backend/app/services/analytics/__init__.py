"""Аналитика истории нарядов: детекторы закономерностей и выводы с рекомендациями."""

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Equipment
from app.services.analytics.data import Scope, load
from app.services.analytics.detectors import DETECTORS, Finding, overview

__all__ = ["Finding", "Scope", "run_detectors"]

_SEVERITY = {"high": 0, "medium": 1, "info": 2}


def _in_scope(f: Finding, scope: Scope, section_equipment: set[int]) -> bool:
    equipment_id = f.refs.get("equipment_id")
    if scope.equipment_id is not None:
        return equipment_id == scope.equipment_id
    if scope.section_id is not None:
        return f.refs.get("section_id") == scope.section_id or equipment_id in section_equipment
    return True


async def run_detectors(session: AsyncSession, scope: Scope | None = None) -> list[Finding]:
    """Находки по срезу. Сравнивать есть смысл только со всем предприятием — поэтому детекторы
    считают по всем данным периода, а срез (участок, оборудование) фильтрует результат."""
    scope = scope or Scope()
    whole = replace(scope, section_id=None, equipment_id=None)
    frames = await load(session, whole)
    findings = [finding for detector in DETECTORS for finding in detector(frames, whole)]

    if scope.section_id is not None or scope.equipment_id is not None:
        section_equipment = set(
            await session.scalars(
                select(Equipment.id).where(Equipment.section_id == scope.section_id)
            )
        )
        findings = [f for f in findings if _in_scope(f, scope, section_equipment)]
        findings += overview(await load(session, scope), scope)
    return sorted(findings, key=lambda f: _SEVERITY[f.severity])
