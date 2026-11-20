import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.routes.admin_dashboard import router as admin_dashboard_router
from api.routes.admin_sources import router as admin_sources_router
from api.routes.chat import FeedbackRequest, record_feedback
from api.routes.chat import router as chat_router
from api.routes.departments import router as departments_router
from db.session import get_db

# Configure root logger for real-time terminal output across all modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

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
    """Application lifespan context manager for startup and shutdown hooks.

    Lightweight startup: heavy ML models (embeddings, reranker, OCR, LLMs)
    are strictly lazy-loaded on-demand when first requested rather than at boot.
    """
    # Clean up any orphaned 'fetching' statuses from previous server restarts
    try:
        import asyncio

        await asyncio.to_thread(run_auto_migrations)

        from sqlalchemy import update

        from db.session import async_session_maker
        from models.source import IngestionSource

        async with async_session_maker() as session:
            stmt = (
                update(IngestionSource)
                .where(IngestionSource.status == "fetching")
                .values(status="idle")
            )
            await session.execute(stmt)
            await session.commit()
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
app.include_router(admin_dashboard_router)
app.include_router(admin_sources_router)
app.include_router(chat_router)
app.include_router(departments_router)


@app.post("/feedback", tags=["Chat"])
async def root_feedback_endpoint(
    payload: FeedbackRequest,
    session: AsyncSession = Depends(get_db),
):
    """Direct root alias for student query feedback (POST /feedback)."""
    return await record_feedback(payload=payload, session=session)


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


@app.get("/admin/jina-usage", tags=["Admin"])
async def jina_usage_check() -> dict:
    """Retrieve token usage statistics for Jina AI API and remaining free-tier capacity."""
    from retrieval.jina_client import jina_token_tracker

    return jina_token_tracker.get_summary()
