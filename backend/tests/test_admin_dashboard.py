import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.session import get_db


@pytest.fixture
def mock_admin_db():
    session = AsyncMock()

    async def mock_execute(stmt):
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = []
        mock_res.scalar.return_value = 0
        mock_res.all.return_value = []
        mock_res.scalar_one_or_none.return_value = None
        return mock_res

    session.execute.side_effect = mock_execute
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_admin_auth_endpoint() -> None:
    """Test admin password verification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid password
        resp = await client.post("/admin/auth/verify", json={"password": "wrong"})
        assert resp.status_code == 401

        # Valid default password
        resp = await client.post("/admin/auth/verify", json={"password": "edusync-admin-2026"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True


@pytest.mark.asyncio
async def test_admin_analytics_endpoint(mock_admin_db) -> None:
    """Test analytics aggregation endpoint returns valid structure."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/analytics")
            assert resp.status_code == 200
            data = resp.json()
            assert "total_queries" in data
            assert "total_documents" in data
            assert "total_chunks" in data
            assert "feedback_stats" in data
            assert "fallback_rate" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_analytics_export_endpoint(mock_admin_db) -> None:
    """Test analytics CSV export endpoint."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/analytics/export")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers["content-type"]
            assert "Timestamp (UTC)" in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_documents_list_endpoint(mock_admin_db) -> None:
    """Test admin documents list with pagination."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/documents?page=1&limit=5")
            assert resp.status_code == 200
            data = resp.json()
            assert "total" in data
            assert "documents" in data
            assert isinstance(data["documents"], list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_conflicts_list_endpoint(mock_admin_db) -> None:
    """Test admin conflicts listing."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/conflicts")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_document_chunks_endpoint(mock_admin_db) -> None:
    """Test retrieving chunks for a specific document."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            test_id = uuid.uuid4()
            resp = await client.get(f"/admin/documents/{test_id}/chunks")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_tools_health_endpoint(mock_admin_db) -> None:
    """Test system health diagnostic endpoint."""
    app.dependency_overrides[get_db] = lambda: mock_admin_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/tools/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "db_ping_ms" in data
            assert "pgvector_installed" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_source_test_url_endpoint() -> None:
    """Test source URL connectivity verification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/sources/test-url", json={"url": "https://ecajmer.ac.in/dummy"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_valid" in data
        assert "message" in data
