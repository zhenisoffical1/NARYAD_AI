"""Тестовые данные для API: небольшой справочник и фото с EXIF."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import piexif
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Brigade,
    Equipment,
    FaultCode,
    Material,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.enums import Criticality


@dataclass
class Refs:
    section: Section
    pump: Equipment
    crusher: Equipment
    code_hydraulic: FaultCode
    oil: Material
    seal: Material
    brigade: Brigade


async def make_refs(session: AsyncSession) -> Refs:
    section = Section(name="Обогащение")
    brigade = Brigade(name="Бригада №1")
    session.add_all([section, brigade])
    await session.flush()
    pump = Equipment(
        name="Насос гидравлический Н-7",
        inv_number="ОБ-007",
        section_id=section.id,
        type="Насос",
        criticality=Criticality.A,
        qr_code="QR-OB-007",
    )
    crusher = Equipment(
        name="Дробилка КМД-1750",
        inv_number="ДР-001",
        section_id=section.id,
        type="Дробилка",
        criticality=Criticality.A,
    )
    code = FaultCode(code="Г-02", category="Г", name="Течь гидравлической системы")
    oil = Material(name="Масло И-40А", unit="л", category="смазочные")
    seal = Material(name="Уплотнение манжетное 50×70", unit="шт", category="уплотнения")
    session.add_all([pump, crusher, code, oil, seal])
    await session.flush()
    norm = TimeNorm(fault_code_id=code.id, norm_hours=Decimal("1.5"))
    session.add(norm)
    await session.flush()
    session.add(TimeNormMaterial(time_norm_id=norm.id, material_id=oil.id, quantity=Decimal("1.5")))
    await session.commit()
    return Refs(section, pump, crusher, code, oil, seal, brigade)


def jpeg_bytes(
    color: tuple[int, int, int] = (120, 120, 120),
    taken_at: datetime | None = None,
    size: tuple[int, int] = (800, 600),
    mark: int = 0,
) -> bytes:
    """JPEG с рисунком (чтобы pHash различался) и, если нужно, временем съёмки в EXIF."""
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([50 + mark * 40, 50, 300 + mark * 40, 300], fill=(255 - color[0], 30, 30))
    draw.ellipse([400, 200 + mark * 30, 700, 500], fill=(20, 200 - mark * 20, 90))
    buf = BytesIO()
    kwargs = {}
    if taken_at is not None:
        # Камера пишет местное время без пояса — как телефон на предприятии
        stamp = taken_at.astimezone(settings.tz).strftime("%Y:%m:%d %H:%M:%S").encode()
        kwargs["exif"] = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: stamp}})
    image.save(buf, "JPEG", quality=90, **kwargs)
    return buf.getvalue()
