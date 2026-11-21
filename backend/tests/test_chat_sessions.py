import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.session import get_db
from models.chat_session import ChatSession


@pytest.fixture
def mock_session_db():
    session_store: dict[uuid.UUID, ChatSession] = {}

    session = AsyncMock()

    async def mock_execute(stmt):
        mock_res = MagicMock()
        items = list(session_store.values())
        mock_res.scalars.return_value.all.return_value = items
        return mock_res

    async def mock_get(entity, entity_id):
        if entity == ChatSession and isinstance(entity_id, uuid.UUID):
            return session_store.get(entity_id)
        return None

    def mock_add(obj):
        if isinstance(obj, ChatSession):
            if not obj.id:
                obj.id = uuid.uuid4()
            if not obj.created_at:
                obj.created_at = datetime.now(UTC)
            if not obj.updated_at:
                obj.updated_at = datetime.now(UTC)
            session_store[obj.id] = obj

    async def mock_delete(obj):
        if isinstance(obj, ChatSession) and obj.id in session_store:
            del session_store[obj.id]

    session.execute.side_effect = mock_execute
    session.get.side_effect = mock_get
    session.add = MagicMock(side_effect=mock_add)
    session.delete.side_effect = mock_delete
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    return session, session_store


@pytest.mark.asyncio
async def test_chat_sessions_crud(mock_session_db):
    mock_db, store = mock_session_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a session
        create_res = await client.post(
            "/chat/sessions",
            json={
                "student_id": "student_101",
                "title": "Exam inquiries",
                "messages": [{"id": "1", "sender": "user", "text": "When are midterms?"}],
            },
        )
        assert create_res.status_code == 200
        data = create_res.json()
        assert data["student_id"] == "student_101"
        assert data["title"] == "Exam inquiries"
        assert len(data["messages"]) == 1
        session_id = data["id"]

        # 2. List sessions
        list_res = await client.get("/chat/sessions?student_id=student_101")
        assert list_res.status_code == 200
        summaries = list_res.json()
        assert len(summaries) >= 1

        # 3. Get single session
        get_res = await client.get(f"/chat/sessions/{session_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == session_id

        # 4. Toggle Pin
        pin_res = await client.post(f"/chat/sessions/{session_id}/pin")
        assert pin_res.status_code == 200
        assert pin_res.json()["is_pinned"] is True

        # 5. Toggle Archive
        arch_res = await client.post(f"/chat/sessions/{session_id}/archive")
        assert arch_res.status_code == 200
        assert arch_res.json()["is_archived"] is True
        assert arch_res.json()["is_pinned"] is False  # Archiving unpins

        # 6. Update session
        update_res = await client.patch(
            f"/chat/sessions/{session_id}",
            json={"title": "Updated Title", "is_archived": False},
        )
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "Updated Title"
        assert update_res.json()["is_archived"] is False

        # 7. Delete session
        del_res = await client.delete(f"/chat/sessions/{session_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

    app.dependency_overrides.clear()
