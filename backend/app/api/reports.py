from dataclasses import asdict
from datetime import date
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, require_role
from app.models import Employee, Order
from app.models.enums import Role
from app.services.orders import ensure_can_view
from app.services.reports import builders
from app.services.reports.model import Period, Report, window
from app.services.reports.pdf import to_pdf
from app.services.reports.xlsx import to_xlsx

router = APIRouter(prefix="/reports", tags=["Отчёты"])

STAFF = require_role(Role.MASTER, Role.BOSS, Role.ADMIN)
Format = Literal["json", "xlsx", "pdf"]
Kind = Literal["orders", "rating", "materials", "downtime"]

MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _respond(report: Report, fmt: Format, filename: str) -> Response:
    if fmt == "json":
        return JSONResponse(jsonable(report))
    data = to_xlsx(report) if fmt == "xlsx" else to_pdf(report)
    name = f"{filename}.{fmt}"
    return Response(
        data,
        media_type=MEDIA[fmt],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


def jsonable(report: Report) -> dict[str, Any]:
    data = asdict(report)
    data["generated_at"] = report.generated_at.isoformat()
    return data


@router.get("/{kind}", summary="Отчёт за период: наряды, рейтинг, материалы, простои")
async def period_report(
    kind: Kind,
    period: Period = "shift",
    date_from: date | None = None,
    date_to: date | None = None,
    section_id: int | None = None,
    format: Format = Query(default="json"),
    _user: Employee = Depends(STAFF),
    session: AsyncSession = Depends(get_session),
) -> Response:
    w = window(period, date_from, date_to)
    if kind == "orders":
        report = await builders.orders_report(session, w, section_id)
    elif kind == "rating":
        report = await builders.rating_report(session, w)
    elif kind == "materials":
        report = await builders.materials_report(session, w, section_id)
    else:
        report = await builders.downtime_report(session, w, section_id)
    stamp = w.start.strftime("%Y-%m-%d")
    return _respond(report, format, f"НарядAI_{report.title.split(':')[0]}_{stamp}")


@router.get("/order/{order_id}", summary="Отчёт по наряду")
async def order_report(
    order_id: int,
    format: Format = Query(default="pdf"),
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    order = await session.get(Order, order_id)
    if order is not None:
        ensure_can_view(order, user)
    report = await builders.order_report(session, order_id)
    return _respond(report, format, f"НарядAI_{report.title}")
