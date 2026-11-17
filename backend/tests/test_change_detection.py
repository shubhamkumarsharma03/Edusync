import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.change_detector import ChangeDetector, ChangeStatus
from ingestion.hasher import compute_hash, normalize_content
from ingestion.schemas import FetchedDocument
from models.document import Document


def test_normalize_and_compute_hash_deterministic() -> None:
    """Test that content normalization produces identical SHA-256 hashes despite trivial whitespace/newline formatting."""
    content1 = "Engineering College Ajmer\nDepartment of CSE\r\nNotice 2026\n\n\n"
    content2 = "  Engineering College Ajmer  \nDepartment of CSE\n\nNotice 2026  "

    hash1 = compute_hash(content1, source_type="html")
    hash2 = compute_hash(content2, source_type="html")

    assert hash1 == hash2
    assert len(hash1) == 64  # Valid SHA-256 length

    # Different text must produce different hash
    content3 = "Engineering College Ajmer\nDepartment of ECE\nNotice 2026"
    hash3 = compute_hash(content3, source_type="html")
    assert hash1 != hash3


def test_normalize_binary_content() -> None:
    """Test raw binary normalization for PDFs."""
    pdf_bytes = b"%PDF-1.4 header and binary payload \x00\x01\x02"
    normalized = normalize_content(pdf_bytes, source_type="pdf")
    assert normalized == pdf_bytes

    hash_pdf = compute_hash(pdf_bytes, source_type="pdf")
    assert len(hash_pdf) == 64


@pytest.mark.asyncio
async def test_detect_new_document() -> None:
    """Test change detector when document is not in database."""
    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/notices/exam_2026.pdf",
        source_type="pdf",
        raw_content=b"Sample PDF Content",
        extracted_text="Exam Notice 2026",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await ChangeDetector.check_document(
        mock_session, fetched, department_id=1, owner="Exam Cell"
    )

    assert result.status == ChangeStatus.NEW
    assert result.requires_reembedding is True
    assert result.source_url == fetched.source_url
    assert result.content_hash == compute_hash(fetched.raw_content, "pdf")
    assert result.metadata.get("department_id") == 1
    assert mock_session.commit.call_count == 0  # No commit needed until ingestion creates row


@pytest.mark.asyncio
async def test_detect_unchanged_document() -> None:
    """Test change detector when document hash matches database record (0 re-embedding)."""
    raw_content = b"Official Circular 2026 Content"
    current_hash = compute_hash(raw_content, "pdf")
    doc_id = uuid.uuid4()

    existing_doc = Document(
        id=doc_id,
        source_url="https://ecajmer.ac.in/notices/circular.pdf",
        source_type="pdf",
        department_id=1,
        owner="HOD",
        content_hash=current_hash,
        status="fresh",
        ingested_at=datetime.now(UTC),
        last_checked_at=datetime.now(UTC),
    )

    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/notices/circular.pdf",
        source_type="pdf",
        raw_content=raw_content,
        extracted_text="Official Circular 2026 Content",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_session.execute.return_value = mock_result

    result = await ChangeDetector.check_document(mock_session, fetched)

    assert result.status == ChangeStatus.UNCHANGED
    assert result.requires_reembedding is False
    assert result.existing_document_id == doc_id
    assert mock_session.commit.call_count == 1  # Committed updated last_checked_at timestamp


@pytest.mark.asyncio
async def test_detect_modified_document() -> None:
    """Test change detector when document content differs (marks status='pending')."""
    doc_id = uuid.uuid4()
    old_content = b"Old Syllabus 2025"
    old_hash = compute_hash(old_content, "pdf")

    existing_doc = Document(
        id=doc_id,
        source_url="https://ecajmer.ac.in/syllabus/cs_sem7.pdf",
        source_type="pdf",
        department_id=1,
        owner="HOD",
        content_hash=old_hash,
        status="fresh",
        ingested_at=datetime.now(UTC),
        last_checked_at=datetime.now(UTC),
    )

    new_content = b"Revised Syllabus 2026 with new subjects"
    new_hash = compute_hash(new_content, "pdf")

    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/syllabus/cs_sem7.pdf",
        source_type="pdf",
        raw_content=new_content,
        extracted_text="Revised Syllabus 2026 with new subjects",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_session.execute.return_value = mock_result

    result = await ChangeDetector.check_document(mock_session, fetched)

    assert result.status == ChangeStatus.MODIFIED
    assert result.requires_reembedding is True
    assert result.content_hash == new_hash
    assert existing_doc.status == "pending"
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
async def test_batch_change_detection() -> None:
    """Test batch evaluation of fetched documents."""
    docs = [
        FetchedDocument(
            source_url="https://ecajmer.ac.in/doc1.pdf",
            source_type="pdf",
            raw_content=b"Doc 1 Content",
            extracted_text="Doc 1",
        ),
        FetchedDocument(
            source_url="https://ecajmer.ac.in/doc2.pdf",
            source_type="pdf",
            raw_content=b"Doc 2 Content",
            extracted_text="Doc 2",
        ),
    ]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    batch_results = await ChangeDetector.check_batch(mock_session, docs)

    assert len(batch_results) == 2
    assert all(r.status == ChangeStatus.NEW for r in batch_results)
