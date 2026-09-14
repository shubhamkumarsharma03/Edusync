import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routes.admin_sources import router as admin_sources_router
from api.routes.chat import router as chat_router
from api.routes.departments import router as departments_router

# Configure root logger for real-time terminal output across all modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks.

    Lightweight startup: heavy ML models (embeddings, reranker, OCR, LLMs)
    are strictly lazy-loaded on-demand when first requested rather than at boot.
    """
    # Clean up any orphaned 'fetching' statuses from previous server restarts
    try:
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


@app.get("/admin/jina-usage", tags=["Admin"])
async def jina_usage_check() -> dict:
    """Retrieve token usage statistics for Jina AI API and remaining free-tier capacity."""
    from retrieval.jina_client import jina_token_tracker

    return jina_token_tracker.get_summary()
