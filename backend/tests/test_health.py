import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify that GET /health returns 200 OK and expected payload."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "EduSync API"
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify that GET / returns service information."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "EduSync API"
    assert "docs_url" in data
