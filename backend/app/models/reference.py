"""Справочники. external_id — ключ для будущей синхронизации с 1С / ERP / ТОиР."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum
from app.models.enums import Criticality


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    equipment: Mapped[list["Equipment"]] = relationship(back_populates="section")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    inv_number: Mapped[str] = mapped_column(String(32), unique=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    type: Mapped[str] = mapped_column(String(80))
    criticality: Mapped[Criticality] = mapped_column(str_enum(Criticality, 1))
    qr_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    section: Mapped[Section] = relationship(back_populates="equipment")


class Brigade(Base):
    __tablename__ = "brigades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)


class FaultCode(Base):
    __tablename__ = "fault_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)  # «М-02»
    category: Mapped[str] = mapped_column(String(2))  # М, Э, Г, П, С
    name: Mapped[str] = mapped_column(String(160))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    norm: Mapped["TimeNorm | None"] = relationship(back_populates="fault_code")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    unit: Mapped[str] = mapped_column(String(16))  # шт, л, кг, м
    category: Mapped[str | None] = mapped_column(String(40))  # смазочные, подшипники, электрика…
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)


class TimeNorm(Base):
    """Норматив по шифру: часы на работу и типичный набор материалов с нормой расхода."""

    __tablename__ = "time_norms"

    id: Mapped[int] = mapped_column(primary_key=True)
    fault_code_id: Mapped[int] = mapped_column(ForeignKey("fault_codes.id"), unique=True)
    norm_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2))

    fault_code: Mapped[FaultCode] = relationship(back_populates="norm")
    materials: Mapped[list["TimeNormMaterial"]] = relationship(
        back_populates="norm", cascade="all, delete-orphan"
    )


class TimeNormMaterial(Base):
    __tablename__ = "time_norm_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_norm_id: Mapped[int] = mapped_column(ForeignKey("time_norms.id", ondelete="CASCADE"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))

    norm: Mapped[TimeNorm] = relationship(back_populates="materials")
    material: Mapped[Material] = relationship()
