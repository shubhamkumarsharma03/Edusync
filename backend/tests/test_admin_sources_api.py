import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from db.session import get_db
from models.source import IngestionSource


@pytest.fixture
def mock_db_session():
    """In-memory mock session for Admin Sources API tests to run in CI without live Postgres."""
    sources_store: dict[uuid.UUID, IngestionSource] = {}

    session = AsyncMock()

    async def mock_execute(stmt):
        mock_res = MagicMock()
        items = list(sources_store.values())

        # Check if querying single source by ID from statement params or where criteria
        found_item = None
        try:
            compiled = stmt.compile()
            for val in compiled.params.values():
                if isinstance(val, uuid.UUID):
                    found_item = sources_store.get(val)
                    break
                elif isinstance(val, str):
                    try:
                        u = uuid.UUID(val)
                        if u in sources_store:
                            found_item = sources_store[u]
                            break
                    except ValueError:
                        pass
        except Exception:
            pass

        mock_res.scalars.return_value.all.return_value = items
        mock_res.scalar.return_value = len(items)
        mock_res.scalar_one_or_none.return_value = found_item
        return mock_res

    async def mock_get(entity, entity_id):
        if isinstance(entity_id, str):
            entity_id = uuid.UUID(entity_id)
        return sources_store.get(entity_id)

    def mock_add(instance):
        if not getattr(instance, "id", None):
            instance.id = uuid.uuid4()
        if getattr(instance, "is_active", None) is None:
            instance.is_active = True
        if getattr(instance, "sync_status", None) is None:
            instance.sync_status = "idle"
        if getattr(instance, "priority", None) is None:
            instance.priority = 0
        if getattr(instance, "documents_count", None) is None:
            instance.documents_count = 0
        if getattr(instance, "chunks_count", None) is None:
            instance.chunks_count = 0
        if getattr(instance, "created_at", None) is None:
            now = datetime.now(UTC)
            instance.created_at = now
            instance.updated_at = now
        sources_store[instance.id] = instance

    async def mock_delete(instance):
        sources_store.pop(instance.id, None)

    async def mock_commit():
        pass

    async def mock_refresh(instance):
        pass

    session.execute = AsyncMock(side_effect=mock_execute)
    session.get = AsyncMock(side_effect=mock_get)
    session.add = MagicMock(side_effect=mock_add)
    session.delete = AsyncMock(side_effect=mock_delete)
    session.commit = AsyncMock(side_effect=mock_commit)
    session.refresh = AsyncMock(side_effect=mock_refresh)

    return session


@pytest.mark.asyncio
async def test_admin_sources_crud_flow(mock_db_session):
    """Verify full CRUD flow for Admin Sources API."""
    app.dependency_overrides[get_db] = lambda: mock_db_session

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
async def test_admin_sources_seed_defaults(mock_db_session):
    """Verify seed defaults populates standard departments."""
    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/admin/sources/seed-defaults")
            assert res.status_code == 200
            sources = res.json()
            assert len(sources) == 4
            slugs = [s["slug"] for s in sources]
            assert "cs-it" in slugs
            assert "examination-section" in slugs
            assert "registrar" in slugs
            assert "academic-section" in slugs
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_live_progress_endpoints():
    """Verify live progress endpoints return valid state and logs."""
    from ingestion.progress import progress_tracker

    test_sid = str(uuid.uuid4())
    progress_tracker.start_source(test_sid, "Live Test Source", total_items=5)
    progress_tracker.update_step(
        phase="ocr_inference",
        step_index=3,
        current_action="Running Baidu PaddleOCR-VL layout analysis",
        next_action="Isolate tables and generate vector embeddings",
        source_id=test_sid,
        log_message="Extracting markdown layout for notice_2026.pdf",
        log_level="ocr",
        log_tag="OCR",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Global live progress
        res_global = await ac.get("/admin/sources/live-progress")
        assert res_global.status_code == 200
        global_data = res_global.json()
        assert global_data["source_name"] == "Live Test Source"
        assert global_data["phase"] == "ocr_inference"
        assert global_data["step_index"] == 3
        assert "Baidu PaddleOCR" in global_data["current_action"]
        assert len(global_data["logs"]) >= 2

        # Source specific live progress
        res_src = await ac.get(f"/admin/sources/{test_sid}/live-progress")
        assert res_src.status_code == 200
        src_data = res_src.json()
        assert src_data["source_id"] == test_sid
        assert src_data["phase"] == "ocr_inference"
