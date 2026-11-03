from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    # Application
    APP_NAME: str = "EduSync API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edusync"

    # Vector Store & Reranker
    VECTOR_STORE_TYPE: str = "pgvector"
    EMBEDDING_MODEL_NAME: str = "bge-m3"
    EMBEDDING_DIM: int = 1024
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    CONFIDENCE_THRESHOLD: float = 0.55

    # Providers ("auto", "jina", "local")
    EMBEDDING_PROVIDER: str = "auto"
    RERANKER_PROVIDER: str = "auto"

    # Jina AI Settings
    JINA_API_KEY: str | None = None
    JINA_EMBEDDING_MODEL: str = "jina-embeddings-v3"
    JINA_RERANKER_MODEL: str = "jina-reranker-v2-base-multilingual"
    JINA_EMBEDDING_TASK_PASSAGE: str = "retrieval.passage"
    JINA_EMBEDDING_TASK_QUERY: str = "retrieval.query"
    JINA_EMBED_BATCH_SIZE: int = 32
    JINA_TIMEOUT: float = 30.0
    JINA_MAX_RETRIES: int = 3

    # OCR Provider Settings
    OCR_PROVIDER: str = "auto"  # "auto", "baidu", "got_ocr"

    # Baidu PaddleOCR Settings (AI Studio)
    BAIDU_OCR_TOKEN: str | None = None  # Also accepts PADDLEOCR_TOKEN from env
    PADDLEOCR_TOKEN: str | None = None
    BAIDU_OCR_API_URL: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    BAIDU_OCR_MODEL: str = "PaddleOCR-VL-1.6"
    BAIDU_OCR_MODE: str = "auto"  # "auto", "async_job", "serving"
    BAIDU_OCR_USE_DOC_ORIENTATION: bool = True
    BAIDU_OCR_USE_DOC_UNWARPING: bool = True
    BAIDU_OCR_USE_TEXTLINE_ORIENTATION: bool = False
    BAIDU_OCR_USE_CHART_RECOGNITION: bool = False
    BAIDU_OCR_VISUALIZE: bool = False
    BAIDU_OCR_POLL_INTERVAL: float = 3.0
    BAIDU_OCR_TIMEOUT: float = 30.0

    # Local GOT-OCR 2.0 Settings (Offline fallback)
    GOT_OCR_MODEL_ID: str = "stepfun-ai/GOT-OCR-2.0-hf"
    GOT_OCR_DEVICE: str = "auto"
    GOT_OCR_MAX_TOKENS: int = 1024
    GOT_OCR_DPI: int = 150
    OCR_MIN_TEXT_THRESHOLD: int = 40
    GOT_OCR_FORMAT: bool = True
    GOT_OCR_CACHE_DIR: str = "models_cache/ocr_cache"

    # LLM API Keys
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GEMINI_ANALYSIS_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str | None = None

    # Celery & Queue
    CELERY_TASK_ALWAYS_EAGER: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"
    REINGEST_INTERVAL_HOURS: int = 6

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
