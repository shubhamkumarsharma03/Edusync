from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routes.admin_sources import router as admin_sources_router
from api.routes.chat import router as chat_router
from api.routes.departments import router as departments_router

settings = get_settings()


def run_auto_migrations() -> None:
    """Run alembic upgrade head programmatically on startup to ensure DB schema is synchronized."""
    import logging
    import os

    from alembic.config import Config

    from alembic import command

    logger = logging.getLogger("uvicorn.error")
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(backend_dir, "alembic.ini")
        if os.path.exists(ini_path):
            alembic_cfg = Config(ini_path)
            alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
            command.upgrade(alembic_cfg, "head")
            logger.info("Auto DB migrations applied successfully to latest head.")
    except Exception as e:
        logger.warning(f"Auto DB migration skipped or failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    import asyncio

    from api.routes.chat import warm_llm_client
    from ingestion.embedder import DocumentEmbedder
    from retrieval.reranker import CrossEncoderReranker

    try:
        await asyncio.to_thread(run_auto_migrations)
        await asyncio.to_thread(DocumentEmbedder.get_model)
        await asyncio.to_thread(CrossEncoderReranker.get_model)
        await warm_llm_client()
    except Exception:
        pass

    yield

    # Shutdown logic (e.g. closing connections)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="EduSync - Self-Updating RAG Chatbot for Institutional Documents",
    lifespan=lifespan,
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(admin_sources_router)
app.include_router(chat_router)
app.include_router(departments_router)


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    """Root info endpoint."""
    return {
        "service": "EduSync API",
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": "EduSync API",
        "version": settings.APP_VERSION,
    }
