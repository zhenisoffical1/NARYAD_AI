from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-on-the-server-0000"


class Settings(BaseSettings):
    """Все настройки — из переменных окружения или .env (корень репозитория или backend/)."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://naryad:naryad@localhost:5432/naryad"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_minutes: int = 12 * 60  # смена + запас
    login_max_attempts: int = 5
    login_lock_minutes: int = 5

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    media_dir: Path = Path("media")
    public_url: str = "http://localhost"

    demo_mode: bool = False

    # Время и смены. С марта 2024 Казахстан живёт в едином поясе UTC+5.
    timezone: str = "Asia/Qostanay"
    day_shift_start_hour: int = 8
    night_shift_start_hour: int = 20

    # Фото
    max_photos_per_kind: int = 5
    max_upload_mb: int = 15
    photo_max_side: int = 1600
    thumb_max_side: int = 480

    # Рейтинг исполнителей: веса составляющих (сумма = 1), обоснование — docs/DECISIONS.md
    rating_weights: dict[str, float] = {
        "quality": 0.35,
        "on_time": 0.25,
        "no_returns": 0.20,
        "volume": 0.15,
        "no_rejects": 0.05,
    }

    # Срок по умолчанию, если мастер не указал (часы) — по приоритету
    deadline_hours_emergency: float = 2
    deadline_hours_high: float = 4
    deadline_hours_normal: float = 8
    deadline_hours_planned: float = 24

    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5-5"
    llm_fast_model: str = "claude-haiku-4-5-20251001"
    # Проверка наряда должна уложиться в 15 с: на один вызов — не больше 12 с, при сбое — правила
    llm_timeout_seconds: float = 12
    llm_effort: str = "low"  # классификация по готовым фактам — глубокое рассуждение не нужно
    # Server-side fallback (Claude API): при отказе модели запрос повторяется на запасной
    llm_server_fallback: bool = True

    # Контроль сроков (ТЗ 6.1). Все пороги — в минутах.
    deadline_check_seconds: int = 30
    remind_before_min: int = 30  # напоминание исполнителю до срока
    unaccepted_min: int = 10  # эскалация мастеру, если наряд не принят
    unaccepted_emergency_min: int = 3
    repeat_min: int = 15  # повтор просрочки и эскалации
    emergency_repeat_min: int = 1  # аварийный — пока не принят
    boss_overdue_min: int = 120  # длительная просрочка — руководителю

    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None  # для ссылки привязки t.me/<имя>?start=…
    telegram_poll_seconds: float = 2

    @property
    def llm_mock(self) -> bool:
        return not self.anthropic_api_key

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
