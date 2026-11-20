import logging
import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.embedder import DocumentEmbedder
from ingestion.hasher import compute_document_hash
from ingestion.schemas import ChunkData, FetchedDocument
from models.chunk import Chunk
from models.document import Document

logger = logging.getLogger(__name__)


def _parse_notice_date(val: Any) -> date | None:
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    val_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(val_str, fmt).date()
            if 1990 <= d.year <= 2035:
                return d
        except ValueError:
            pass
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val_str)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if 1990 <= d.year <= 2035:
                return d
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", val_str)
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if 1990 <= d.year <= 2035:
                return d
        except ValueError:
            pass
    return None


BOILERPLATE_TITLES = {
    "engineering college ajmer",
    "govt. engineering college, ajmer",
    "government engineering college, ajmer",
    "govt engineering college ajmer",
    "government engineering college ajmer",
    "office of the principal",
    "office order",
    "circular",
    "notice",
    "urgent notice",
}


def _clean_extracted_title(candidate: str | None) -> str | None:
    if not candidate:
        return None
    c = candidate.strip()
    c_lower = c.lower()
    if (
        c_lower in BOILERPLATE_TITLES
        or c_lower.startswith("department of")
        or c_lower.startswith("table")
    ):
        return None
    return c


def _extract_document_meta(
    fetched: FetchedDocument, chunks: list[ChunkData]
) -> tuple[str | None, str | None, date | None, int | None]:
    # 1. Clean Title ground truth from portal listing
    title = _clean_extracted_title(fetched.metadata.get("title"))

    sno = fetched.metadata.get("sno") or fetched.metadata.get("notice_sno")
    raw_date = (
        fetched.metadata.get("notice_date")
        or fetched.metadata.get("date")
        or fetched.metadata.get("posted_date")
    )
    portal_id = fetched.metadata.get("portal_id") or fetched.metadata.get("id")

    # 2. Extract from chunks if missing
    if not title or not sno or not raw_date:
        for c in chunks:
            if not title:
                m_notice = re.search(r"\[Notice:\s*([^|\n\r]+)", c.content)
                if m_notice:
                    cand = _clean_extracted_title(m_notice.group(1))
                    if cand:
                        title = cand
                if not title:
                    m = re.search(r"^#\s+([^#\n\r]+)$", c.content, re.MULTILINE)
                    if m:
                        cand = _clean_extracted_title(m.group(1))
                        if cand:
                            title = cand
            if not sno:
                m = re.search(r"\*\*Notice S\.No:\*\*\s*([^\n\r]+)", c.content)
                if m:
                    sno = m.group(1).strip()
            if not raw_date:
                m = re.search(r"\*\*Date:\*\*\s*([^\n\r]+)", c.content)
                if m:
                    raw_date = m.group(1).strip()
            if title and sno and raw_date:
                break

    # 3. Fallback extraction from full extracted text
    if not title or not sno or not raw_date:
        text = fetched.extracted_text
        if not title:
            m = re.search(r"^#\s+([^#\n\r]+)$", text, re.MULTILINE)
            if m:
                cand = _clean_extracted_title(m.group(1))
                if cand:
                    title = cand
        if not sno:
            m = re.search(r"\*\*Notice S\.No:\*\*\s*([^\n\r]+)", text)
            if m:
                sno = m.group(1).strip()
        if not raw_date:
            m = re.search(r"\*\*Date:\*\*\s*([^\n\r]+)", text)
            if m:
                raw_date = m.group(1).strip()

    if not sno:
        m = re.search(r"(20\d{2}WEB\d{4})", fetched.source_url)
        if m:
            sno = m.group(1)

    parsed_date = _parse_notice_date(raw_date)

    parsed_portal_id = None
    if portal_id is not None:
        try:
            parsed_portal_id = int(portal_id)
        except (ValueError, TypeError):
            pass
    if parsed_portal_id is None and sno:
        m = re.search(r"WEB(\d+)", sno, re.IGNORECASE)
        if m:
            try:
                parsed_portal_id = int(m.group(1))
            except (ValueError, TypeError):
                pass

    return title, sno, parsed_date, parsed_portal_id


# Alias for backward compatibility
_extract_sno_and_date = _extract_document_meta


async def upsert_document_and_chunks(
    session: AsyncSession,
    fetched: FetchedDocument,
    chunks: list[ChunkData],
    department_id: int | None = None,
    owner: str | None = None,
    embedder: DocumentEmbedder | None = None,
) -> tuple[Document, list[Chunk]]:
    """Upsert document and its embedded chunks into PostgreSQL + pgvector.

    - Inserts new Document or updates existing Document (setting status='fresh').
    - Purges obsolete chunks if the document was previously ingested.
    - Computes 384-d vector embeddings for all new chunks.
    - Inserts Chunk rows and updates last_verified timestamp.
    """
    if embedder is None:
        embedder = DocumentEmbedder()

    computed_hash = compute_document_hash(fetched)
    dept_id = department_id
    doc_owner = owner or fetched.metadata.get("owner")
    now = datetime.now(UTC)
    doc_title, notice_sno, notice_date, portal_id = _extract_document_meta(fetched, chunks)

    # 1. Query existing document
    stmt = select(Document).where(Document.source_url == fetched.source_url)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        # Create new document record
        document = Document(
            source_url=fetched.source_url,
            source_type=fetched.source_type,
            department_id=dept_id,
            owner=doc_owner,
            content_hash=computed_hash,
            status="fresh",
            title=doc_title,
            notice_sno=notice_sno,
            notice_date=notice_date,
            portal_id=portal_id,
            ingested_at=now,
            last_checked_at=now,
        )
        session.add(document)
        await session.flush()
        logger.info(f"Created new document record: {document.id} ({fetched.source_url})")
    else:
        # Purge obsolete chunks from previous ingestion version
        await session.execute(delete(Chunk).where(Chunk.document_id == document.id))

        # Update existing document metadata and hash
        document.content_hash = computed_hash
        document.status = "fresh"
        if dept_id is not None:
            document.department_id = dept_id
        if doc_owner:
            document.owner = doc_owner
        if doc_title:
            document.title = doc_title
        if notice_sno:
            document.notice_sno = notice_sno
        if notice_date:
            document.notice_date = notice_date
        if portal_id is not None:
            document.portal_id = portal_id
        document.last_checked_at = now
        document.ingested_at = now
        logger.info(
            f"Updated document record & purged old chunks: {document.id} ({fetched.source_url})"
        )

    # 2. Compute vector embeddings for all chunks
    embeddings: list[list[float]] = []
    if chunks:
        import inspect

        aembed = getattr(embedder, "aembed_chunks", None)
        if callable(aembed) and inspect.iscoroutinefunction(aembed):
            embeddings = await aembed(chunks)
        elif callable(aembed) and inspect.iscoroutine(res := aembed(chunks)):
            embeddings = await res
        else:
            embeddings = embedder.embed_chunks(chunks)

    # 3. Create Chunk database records
    chunk_records: list[Chunk] = []
    for idx, chunk_data in enumerate(chunks):
        embedding_vec = embeddings[idx] if idx < len(embeddings) else None
        chunk_obj = Chunk(
            document_id=document.id,
            content=chunk_data.content,
            token_count=chunk_data.token_count,
            embedding=embedding_vec,
            last_verified=now,
        )
        chunk_records.append(chunk_obj)

    if chunk_records:
        session.add_all(chunk_records)

    await session.commit()
    await session.refresh(document)
    logger.info(f"Successfully upserted document {document.id} with {len(chunk_records)} chunks.")

    return document, chunk_records
