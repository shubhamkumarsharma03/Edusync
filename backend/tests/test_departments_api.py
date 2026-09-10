from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.session import get_db
from models.department import Department


@pytest.fixture
def mock_dept_session():
    """In-memory mock session for testing Department endpoints with simple IDs."""
    dept_store: dict[int, Department] = {}
    id_counter = [1]

    session = AsyncMock()

    async def mock_execute(stmt):
        mock_res = MagicMock()
        items = list(dept_store.values())

        found_item = None
        try:
            compiled = stmt.compile()
            for val in compiled.params.values():
                if isinstance(val, int) and val in dept_store:
                    found_item = dept_store[val]
                    break
        except Exception:
            pass

        mock_res.scalars.return_value.all.return_value = items
        mock_res.scalar_one_or_none.return_value = found_item
        return mock_res

    session.execute.side_effect = mock_execute

    def mock_add(obj):
        if isinstance(obj, Department):
            if obj.id is None:
                obj.id = id_counter[0]
                id_counter[0] += 1
            if not obj.created_at:
                obj.created_at = datetime.now(UTC)
            if not obj.updated_at:
                obj.updated_at = datetime.now(UTC)
            dept_store[obj.id] = obj

    session.add = MagicMock(side_effect=mock_add)

    async def mock_commit():
        return None

    async def mock_refresh(obj):
        if isinstance(obj, Department):
            if obj.id is None:
                obj.id = id_counter[0]
                id_counter[0] += 1
            if not obj.created_at:
                obj.created_at = datetime.now(UTC)
            if not obj.updated_at:
                obj.updated_at = datetime.now(UTC)
            dept_store[obj.id] = obj
        return None

    async def mock_delete(obj):
        if isinstance(obj, Department) and obj.id in dept_store:
            del dept_store[obj.id]

    session.commit.side_effect = mock_commit
    session.refresh.side_effect = mock_refresh
    session.delete.side_effect = mock_delete

    return session


@pytest.mark.asyncio
async def test_department_crud_simple_ids(mock_dept_session):
    """Test Department CRUD operations with simple integer IDs."""
    app.dependency_overrides[get_db] = lambda: mock_dept_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Create a department
            res = await ac.post(
                "/admin/departments",
                json={
                    "name": "Computer Science and Engineering",
                    "code": "CSE",
                    "category": "Engineering",
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert data["id"] == 1
            assert data["name"] == "Computer Science and Engineering"
            assert data["code"] == "CSE"
            assert data["slug"] == "computer-science-and-engineering"

            # 2. List departments
            res_list = await ac.get("/admin/departments")
            assert res_list.status_code == 200
            list_data = res_list.json()
            assert len(list_data) == 1
            assert list_data[0]["id"] == 1

            # 3. Get single department
            res_get = await ac.get("/admin/departments/1")
            assert res_get.status_code == 200
            assert res_get.json()["id"] == 1

            # 4. Update department
            res_update = await ac.put(
                "/admin/departments/1",
                json={"code": "CS-IT"},
            )
            assert res_update.status_code == 200
            assert res_update.json()["code"] == "CS-IT"

            # 5. Delete department
            res_del = await ac.delete("/admin/departments/1")
            assert res_del.status_code == 204
    finally:
        app.dependency_overrides.pop(get_db, None)
