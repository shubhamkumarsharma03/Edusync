import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.session import get_db
from models.query_log import QueryLog


@pytest.mark.asyncio
async def test_feedback_endpoint_records_feedback() -> None:
    """Test that POST /chat/feedback updates feedback in QueryLog."""
    query_id = uuid.uuid4()
    mock_log = QueryLog(
        id=query_id,
        question="When is Mid-term exam?",
        answer="Mid-term exam is from Nov 20",
        confidence_score=0.95,
        feedback=None,
    )

    async def override_get_db():
        from unittest.mock import AsyncMock, MagicMock

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log
        session.execute.return_value = mock_result
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/chat/feedback",
                json={"query_id": str(query_id), "feedback": "up"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["feedback"] == "up"
            assert mock_log.feedback == "up"
    finally:
        app.dependency_overrides.clear()
