from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class AppState(Base):
    """Служебные значения: например, где заканчивается сгенерированная история (для демо-сброса)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
