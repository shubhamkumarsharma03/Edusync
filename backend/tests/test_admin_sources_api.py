import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.config import get_settings
from api.main import app
from db.session import get_db

settings = get_settings()


@pytest.fixture
async def async_test_session():
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with test_session_maker() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_admin_sources_crud_flow(async_test_session):
    """Verify full CRUD flow for Admin Sources API."""
    app.dependency_overrides[get_db] = lambda: async_test_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Create source
            payload = {
                "name": "Test CSE Circulars",
                "url": "https://www.ecajmer.ac.in/departments/cs-it/circulars",
                "department": "Computer Science and Engineering",
                "category": "circulars",
                "initial_fetch_limit": 50,
                "subsequent_fetch_limit": 20,
            }
            res_create = await ac.post("/admin/sources", json=payload)
            assert res_create.status_code == 201
            created_data = res_create.json()
            assert created_data["name"] == "Test CSE Circulars"
            assert created_data["slug"] == "cs-it"
            source_id = created_data["id"]

            # 2. Get list
            res_list = await ac.get("/admin/sources")
            assert res_list.status_code == 200
            sources = res_list.json()
            assert any(s["id"] == source_id for s in sources)

            # 3. Update source
            res_update = await ac.put(
                f"/admin/sources/{source_id}",
                json={"name": "Updated CSE Circulars", "priority": 10},
            )
            assert res_update.status_code == 200
            assert res_update.json()["name"] == "Updated CSE Circulars"
            assert res_update.json()["priority"] == 10

            # 4. Delete source
            res_del = await ac.delete(f"/admin/sources/{source_id}")
            assert res_del.status_code == 204

            # 5. Verify deleted
            res_get_deleted = await ac.get(f"/admin/sources/{source_id}")
            assert res_get_deleted.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_admin_sources_seed_defaults(async_test_session):
    """Verify seed defaults populates standard departments."""
    app.dependency_overrides[get_db] = lambda: async_test_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/admin/sources/seed-defaults")
            assert res.status_code == 200
            sources = res.json()
            assert len(sources) >= 10
            slugs = [s["slug"] for s in sources]
            assert "cs-it" in slugs
            assert "ce" in slugs
            assert "registrar" in slugs
    finally:
        app.dependency_overrides.pop(get_db, None)
