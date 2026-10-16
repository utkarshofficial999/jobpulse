from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/pulseai"
    )

    # Redis & Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # Connector Defaults
    DEFAULT_DOMAIN_RATE_LIMIT: float = 5.0  # requests per second
    DEFAULT_TIMEOUT_CONNECT: float = 5.0
    DEFAULT_TIMEOUT_READ: float = 25.0
    MAX_CRAWL_RETRIES: int = 3

    # Notifications
    TELEGRAM_BOT_TOKEN: str | None = None

    # LLM API
    GEMINI_API_KEY: str | None = None


settings = Settings()
