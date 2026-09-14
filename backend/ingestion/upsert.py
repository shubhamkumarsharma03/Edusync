import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.embedder import DocumentEmbedder
from ingestion.hasher import compute_document_hash
from ingestion.schemas import ChunkData, FetchedDocument
from models.chunk import Chunk
from models.document import Document

logger = logging.getLogger(__name__)


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
