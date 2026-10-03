from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum, utcnow
from app.models.employee import Employee
from app.models.enums import OrderStatus, OrderType, PhotoKind, Priority
from app.models.reference import Brigade, Equipment, FaultCode, Material, Section


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status_deadline", "status", "deadline_at"),
        Index("ix_orders_assignee_status", "assignee_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True)
    type: Mapped[OrderType] = mapped_column(str_enum(OrderType, 12))
    priority: Mapped[Priority] = mapped_column(str_enum(Priority, 12))
    status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus, 16), index=True)

    description: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)

    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    brigade_id: Mapped[int | None] = mapped_column(ForeignKey("brigades.id"))
    master_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)

    deadline_at: Mapped[datetime]
    norm_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Форма закрытия
    fault_code_id: Mapped[int | None] = mapped_column(ForeignKey("fault_codes.id"))
    works_done: Mapped[str | None] = mapped_column(Text)
    no_materials: Mapped[bool] = mapped_column(default=False)
    closing_comment: Mapped[str | None] = mapped_column(Text)

    # Время всех переходов (последнее вхождение в статус)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    issued_at: Mapped[datetime | None]
    queued_at: Mapped[datetime | None]
    accepted_at: Mapped[datetime | None]
    rejected_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    paused_at: Mapped[datetime | None]
    done_at: Mapped[datetime | None]
    review_at: Mapped[datetime | None]
    rework_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    # Оборудование остановлено из-за неисправности: простой считается от выдачи до «Исполнено»
    equipment_stopped: Mapped[bool] = mapped_column(default=False)
    downtime_minutes: Mapped[int | None]

    # Отметки контроля сроков — чтобы планировщик не слал одно и то же дважды
    reminder_sent_at: Mapped[datetime | None]
    overdue_notified_at: Mapped[datetime | None]
    escalated_at: Mapped[datetime | None]
    boss_notified_at: Mapped[datetime | None]

    section: Mapped[Section] = relationship()
    equipment: Mapped[Equipment] = relationship()
    assignee: Mapped[Employee | None] = relationship(foreign_keys=[assignee_id])
    master: Mapped[Employee] = relationship(foreign_keys=[master_id])
    brigade: Mapped[Brigade | None] = relationship()
    fault_code: Mapped[FaultCode | None] = relationship()
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", order_by="OrderEvent.id", cascade="all, delete-orphan"
    )
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="order", order_by="Photo.id", cascade="all, delete-orphan"
    )
    writeoffs: Mapped[list["MaterialWriteoff"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderEvent(Base):
    """Журнал: кто, что, когда. Пишется на каждый переход и каждое изменение наряда."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))  # None — система
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[OrderStatus | None] = mapped_column(str_enum(OrderStatus, 16))
    to_status: Mapped[OrderStatus | None] = mapped_column(str_enum(OrderStatus, 16))
    reason: Mapped[str | None] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    order: Mapped[Order] = relationship(back_populates="events")
    actor: Mapped[Employee | None] = relationship()


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[PhotoKind] = mapped_column(str_enum(PhotoKind, 8))
    path: Mapped[str] = mapped_column(String(255))
    thumb_path: Mapped[str] = mapped_column(String(255))
    taken_at: Mapped[datetime | None]  # из EXIF
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow)
    phash: Mapped[str | None] = mapped_column(String(32), index=True)
    width: Mapped[int | None]
    height: Mapped[int | None]
    size_bytes: Mapped[int | None]
    author_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    order: Mapped[Order] = relationship(back_populates="photos")


class MaterialWriteoff(Base):
    __tablename__ = "material_writeoffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit: Mapped[str] = mapped_column(String(16))

    order: Mapped[Order] = relationship(back_populates="writeoffs")
    material: Mapped[Material] = relationship()


class Notification(Base):
    """Лента уведомлений в PWA — дублирует всё, что уходит в Telegram."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    read_at: Mapped[datetime | None]
