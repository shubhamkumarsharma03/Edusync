import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.embedder import DocumentEmbedder
from models.chunk import Chunk
from models.document import Document
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class VectorSearcher:
    """Performs Approximate Nearest Neighbor (ANN) dense vector search against pgvector chunks."""

    def __init__(self, embedder: DocumentEmbedder | None = None) -> None:
        self.embedder = embedder or DocumentEmbedder()

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 20,
        query_embedding: list[float] | None = None,
        allowed_statuses: list[str] | None = None,
        departments: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Search top-k most similar chunks using cosine similarity in pgvector.

        Strictly enforces conflict and stale document exclusion by filtering on document status.
        Supports optional filtering by department.
        """
        if not query and not query_embedding:
            return []

        if query_embedding is None:
            import inspect

            aembed = getattr(self.embedder, "aembed_texts", None)
            if callable(aembed) and inspect.iscoroutinefunction(aembed):
                embeddings = await aembed([query], task="retrieval.query")
            elif callable(aembed) and inspect.iscoroutine(
                res := aembed([query], task="retrieval.query")
            ):
                embeddings = await res
            else:
                embeddings = self.embedder.embed_texts([query])
            if not embeddings:
                return []
            query_embedding = embeddings[0]

        allowed = allowed_statuses if allowed_statuses is not None else ["fresh"]

        # Compute cosine distance using pgvector operator
        distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")

        conditions = [
            Document.status.in_(allowed),
            Chunk.embedding.is_not(None),
        ]
        if departments:
            conditions.append(Document.department.in_(departments))

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Chunk.token_count,
                Chunk.last_verified,
                Document.source_url,
                Document.department,
                Document.owner,
                distance_expr,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(*conditions)
            .order_by(distance_expr.asc())
            .limit(top_k)
        )

        result = await session.execute(stmt)
        rows = result.all()

        retrieved_chunks: list[RetrievedChunk] = []
        for rank, row in enumerate(rows, start=1):
            # Cosine similarity in [0, 1] for normalized embeddings
            # cosine_distance is 1 - cosine_similarity
            distance = float(row.distance) if row.distance is not None else 1.0
            similarity = max(0.0, min(1.0, 1.0 - distance))

            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    score=similarity,
                    vector_score=similarity,
                    source_url=row.source_url,
                    department=row.department,
                    owner=row.owner,
                    last_verified=row.last_verified,
                    token_count=row.token_count,
                    rank=rank,
                )
            )

        logger.debug(f"Vector search for '{query}' returned {len(retrieved_chunks)} results.")
        return retrieved_chunks
