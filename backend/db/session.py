import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.config import get_settings

settings = get_settings()

# Clean DB URL and configure SSL for cloud databases (Neon, Supabase, AWS)
db_url = settings.DATABASE_URL
connect_args: dict = {}

if "sslmode=" in db_url or "ssl=" in db_url:
    # Strip query params for asyncpg and use standard SSL context
    db_url = db_url.split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ctx
elif not any(h in db_url for h in ["localhost", "127.0.0.1", "::1"]):
    # Remote cloud host -> enable SSL
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ctx

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get a database session."""
    async with async_session_maker() as session:
        yield session
