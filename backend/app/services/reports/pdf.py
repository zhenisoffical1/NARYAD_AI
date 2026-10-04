"""Отчёт в PDF: HTML-шаблон Jinja2 → WeasyPrint.

WeasyPrint нужны системные библиотеки Pango (в Docker-образе они есть). Если их нет — понятная
ошибка вместо падения: Excel и экранный отчёт при этом работают.
"""

from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.errors import Conflict
from app.services.reports.model import Report, fmt_dt

HERE = Path(__file__).parent
WIDE = 7  # таблица шире — альбомный лист


@cache
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"])
    )


def render_html(report: Report) -> str:
    landscape = any(len(t.columns) >= WIDE for t in report.tables)
    return (
        _env()
        .get_template("report.html")
        .render(
            report=report,
            landscape=landscape,
            logo=(HERE / "assets" / "km-logo-white.png").as_uri(),
            generated=fmt_dt(report.generated_at),
        )
    )


def to_pdf(report: Report) -> bytes:
    try:
        from weasyprint import HTML  # тяжёлый импорт с системными библиотеками — по требованию
    except OSError as exc:
        raise Conflict(
            "PDF на этом сервере недоступен: не установлены библиотеки Pango. "
            "Выгрузите отчёт в Excel или запустите систему в Docker."
        ) from exc
    pdf: bytes = HTML(string=render_html(report), base_url=str(HERE)).write_pdf()
    return pdf
