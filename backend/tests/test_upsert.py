import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.change_detector import ChangeStatus, DetectionResult
from ingestion.embedder import DocumentEmbedder
from ingestion.pipeline import IngestionSummary, ingest_document
from ingestion.schemas import ChunkData, FetchedDocument
from ingestion.upsert import upsert_document_and_chunks
from models.document import Document


def test_embedder_output_dimensions() -> None:
    """Test that DocumentEmbedder produces 384-dimensional dense vector embeddings."""
    embedder = DocumentEmbedder()
    mock_model = MagicMock()
    mock_emb = MagicMock()
    mock_emb.tolist.return_value = [0.1] * 384
    mock_model.encode.return_value = [mock_emb]

    embedder._model = mock_model
    results = embedder.embed_texts(["Engineering College Ajmer Circular"])

    assert len(results) == 1
    assert len(results[0]) == 384
    assert isinstance(results[0][0], float)


@pytest.mark.asyncio
async def test_upsert_new_document() -> None:
    """Test upserting a new document and inserting chunk vector records."""
    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/notices/exam_notice.pdf",
        source_type="pdf",
        raw_content=b"Sample PDF Content 2026",
        extracted_text="Exam Notice 2026",
    )

    chunks = [
        ChunkData(content="Chunk 1: Mid-term schedule", token_count=50, chunk_index=0),
        ChunkData(content="Chunk 2: Seating plan", token_count=45, chunk_index=1),
    ]

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_embedder = MagicMock()
    mock_embedder.embed_chunks.return_value = [[0.1] * 384, [0.2] * 384]

    doc, chunk_records = await upsert_document_and_chunks(
        session=mock_session,
        fetched=fetched,
        chunks=chunks,
        department="CSE",
        owner="Exam Cell",
        embedder=mock_embedder,
    )

    assert doc.source_url == fetched.source_url
    assert doc.department == "CSE"
    assert doc.status == "fresh"
    assert len(chunk_records) == 2
    assert chunk_records[0].content == "Chunk 1: Mid-term schedule"
    assert len(chunk_records[0].embedding) == 384
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
async def test_upsert_modified_document_purges_old_chunks() -> None:
    """Test that modifying an existing document purges obsolete chunks and commits new ones."""
    doc_id = uuid.uuid4()
    existing_doc = Document(
        id=doc_id,
        source_url="https://ecajmer.ac.in/syllabus/cs_sem7.pdf",
        source_type="pdf",
        department="CSE",
        owner="HOD",
        content_hash="old_hash_123",
        status="pending",
        ingested_at=datetime.now(UTC),
        last_checked_at=datetime.now(UTC),
    )

    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/syllabus/cs_sem7.pdf",
        source_type="pdf",
        raw_content=b"New Revised Syllabus 2026",
        extracted_text="New Revised Syllabus 2026",
    )

    new_chunks = [
        ChunkData(content="Revised Syllabus Core Units", token_count=80, chunk_index=0),
    ]

    mock_session = AsyncMock()
    mock_session.add_all = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_session.execute.return_value = mock_result

    mock_embedder = MagicMock()
    mock_embedder.embed_chunks.return_value = [[0.5] * 384]

    doc, chunk_records = await upsert_document_and_chunks(
        session=mock_session,
        fetched=fetched,
        chunks=new_chunks,
        department="CSE",
        owner="HOD",
        embedder=mock_embedder,
    )

    assert doc.id == doc_id
    assert doc.status == "fresh"
    assert len(chunk_records) == 1
    # Check that delete statement was executed on session
    assert mock_session.execute.call_count >= 2  # select + delete
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
async def test_ingest_document_pipeline_lifecycle() -> None:
    """Test full ingest_document pipeline for unchanged vs modified sources."""
    mock_session = AsyncMock()

    # Case 1: Unchanged document (0 re-embedding invariant)
    mock_detection_unchanged = DetectionResult(
        source_url="https://ecajmer.ac.in/notice.pdf",
        status=ChangeStatus.UNCHANGED,
        content_hash="hash_abc",
        existing_document_id=uuid.uuid4(),
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "ingestion.pipeline.fetch_document",
            AsyncMock(
                return_value=FetchedDocument(
                    source_url="https://ecajmer.ac.in/notice.pdf",
                    source_type="pdf",
                    raw_content=b"Notice content",
                    extracted_text="Notice content",
                )
            ),
        )
        mp.setattr(
            "ingestion.pipeline.ChangeDetector.check_document",
            AsyncMock(return_value=mock_detection_unchanged),
        )

        summary: IngestionSummary = await ingest_document(
            session=mock_session,
            source="https://ecajmer.ac.in/notice.pdf",
        )

        assert summary.status == "unchanged"
        assert summary.reembedded is False
        assert summary.chunks_count == 0
