import logging
import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.chunk import Chunk
from models.document import Document
from models.department import Department
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class KeywordSearcher:
    """Performs keyword search using PostgreSQL Full-Text Search (FTS) with BM25 / ts_rank scoring."""

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Simple alphanumeric tokenizer for BM25 and keyword queries."""
        return re.findall(r"\b\w+\b", text.lower())

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 20,
        allowed_statuses: list[str] | None = None,
        departments: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Execute database-backed full text keyword search against chunks.

        Strictly enforces conflict and stale document exclusion by filtering on document status.
        Supports optional filtering by department.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        allowed = allowed_statuses if allowed_statuses is not None else ["fresh"]

        tsquery = func.plainto_tsquery("english", cleaned_query)
        tsvector = func.to_tsvector("english", Chunk.content)
        rank_expr = func.ts_rank_cd(tsvector, tsquery).label("rank_score")

        base_conditions = [
            Document.status.in_(allowed),
            tsvector.op("@@")(tsquery),
        ]
        if departments:
            base_conditions.append(Department.name.in_(departments))

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Chunk.token_count,
                Chunk.last_verified,
                Document.source_url,
                Department.name.label("department"),
                Document.owner,
                rank_expr,
            )
            .join(Document, Chunk.document_id == Document.id)
            .outerjoin(Department, Document.department_id == Department.id)
            .where(*base_conditions)
            .order_by(rank_expr.desc())
            .limit(top_k)
        )

        results = (await session.execute(stmt)).all()

        # Resilient FTS Fallback: If strict AND query yields 0 results, fall back to OR disjunction
        if not results and len(cleaned_query.split()) > 1:
            words = [w for w in cleaned_query.split() if len(w) > 1]
            if words:
                or_query_str = " OR ".join(words)
                fallback_tsquery = func.websearch_to_tsquery("english", or_query_str)
                fallback_rank = func.ts_rank_cd(tsvector, fallback_tsquery).label("rank_score")
                fallback_conditions = [
                    Document.status.in_(allowed),
                    tsvector.op("@@")(fallback_tsquery),
                ]
                if departments:
                    fallback_conditions.append(Department.name.in_(departments))

                fallback_stmt = (
                    select(
                        Chunk.id,
                        Chunk.document_id,
                        Chunk.content,
                        Chunk.token_count,
                        Chunk.last_verified,
                        Document.source_url,
                        Department.name.label("department"),
                        Document.owner,
                        fallback_rank,
                    )
                    .join(Document, Chunk.document_id == Document.id)
                    .outerjoin(Department, Document.department_id == Department.id)
                    .where(*fallback_conditions)
                    .order_by(fallback_rank.desc())
                    .limit(top_k)
                )
                results = (await session.execute(fallback_stmt)).all()

        rows = results

        retrieved_chunks: list[RetrievedChunk] = []
        for rank, row in enumerate(rows, start=1):
            score = float(row.rank_score) if row.rank_score is not None else 0.0
            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    score=score,
                    keyword_score=score,
                    source_url=row.source_url,
                    department=row.department,
                    owner=row.owner,
                    last_verified=row.last_verified,
                    token_count=row.token_count,
                    rank=rank,
                )
            )

        logger.debug(f"Keyword search for '{query}' returned {len(retrieved_chunks)} results.")
        return retrieved_chunks

    @classmethod
    def score_chunks_with_bm25(
        cls,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        """Rank a collection of in-memory chunks using the rank_bm25 (BM25Okapi) algorithm."""
        if not chunks or not query.strip():
            return list(chunks)

        tokenized_corpus = [cls.tokenize(c.content) for c in chunks]
        tokenized_query = cls.tokenize(query)

        if not tokenized_query:
            return list(chunks)

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)

        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        ranked_results: list[tuple[float, RetrievedChunk]] = []
        for chunk, score in zip(chunks, scores, strict=False):
            norm_score = float(score) / max_score if max_score > 0 else 0.0
            chunk.keyword_score = float(score)
            chunk.score = norm_score
            ranked_results.append((float(score), chunk))

        ranked_results.sort(key=lambda x: x[0], reverse=True)

        res: list[RetrievedChunk] = []
        for rank, (_, chunk) in enumerate(ranked_results[:top_k], start=1):
            chunk.rank = rank
            res.append(chunk)

        return res
