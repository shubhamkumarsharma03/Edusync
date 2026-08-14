from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    # Application
    APP_NAME: str = "EduSync API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edusync"

    # Vector Store
    VECTOR_STORE_TYPE: str = "pgvector"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CONFIDENCE_THRESHOLD: float = 0.55

    # LLM API Keys
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # Celery & Queue
    CELERY_TASK_ALWAYS_EAGER: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
