from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum, utcnow
from app.models.enums import Role, Shift
from app.models.reference import Brigade


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(40), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[Role] = mapped_column(str_enum(Role, 12), index=True)
    specialty: Mapped[str | None] = mapped_column(String(60))  # слесарь-ремонтник, электромонтёр…
    grade: Mapped[int | None]  # разряд
    brigade_id: Mapped[int | None] = mapped_column(ForeignKey("brigades.id"), index=True)
    shift: Mapped[Shift | None] = mapped_column(str_enum(Shift, 8))
    # Присутствие на смене. В проде заполняется из табеля / СКУД, сейчас — сидом и мастером.
    on_shift: Mapped[bool] = mapped_column(default=False)
    pin_hash: Mapped[str] = mapped_column(String(160))
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    brigade: Mapped[Brigade | None] = relationship()

    @property
    def short_name(self) -> str:
        """«Ахметов Ерлан Каиртаевич» → «Ахметов Е.» — формат из ТЗ для уведомлений."""
        parts = self.full_name.split()
        if len(parts) < 2:
            return self.full_name
        return f"{parts[0]} {parts[1][0]}."
