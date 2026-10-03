from functools import lru_cache
from pathlib import Path

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

    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5-5"
    llm_fast_model: str = "claude-haiku-4-5-20251001"

    telegram_bot_token: str | None = None

    @property
    def llm_mock(self) -> bool:
        return not self.anthropic_api_key

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
