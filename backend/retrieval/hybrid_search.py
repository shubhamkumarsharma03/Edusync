import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.embedder import DocumentEmbedder
from retrieval.keyword_search import KeywordSearcher
from retrieval.query_normalizer import query_normalizer
from retrieval.schemas import RetrievedChunk
from retrieval.vector_search import VectorSearcher

logger = logging.getLogger(__name__)


class HybridSearcher:
    """Combines vector dense search and full-text keyword search using Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        embedder: DocumentEmbedder | None = None,
        vector_searcher: VectorSearcher | None = None,
        keyword_searcher: KeywordSearcher | None = None,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
    ) -> None:
        self.embedder = embedder or DocumentEmbedder()
        self.vector_searcher = vector_searcher or VectorSearcher(embedder=self.embedder)
        self.keyword_searcher = keyword_searcher or KeywordSearcher()
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    def reciprocal_rank_fusion(
        self,
        vector_results: list[RetrievedChunk],
        keyword_results: list[RetrievedChunk],
        top_k: int = 20,
        target_departments: list[str] | None = None,
        dept_boost: float = 1.3,
        target_semesters: list[str] | None = None,
        target_branches: list[str] | None = None,
        apply_recency: bool = False,
    ) -> list[RetrievedChunk]:
        """Merge and deduplicate vector and keyword search results using Reciprocal Rank Fusion (RRF).

        Formula: RRF_score(d) = sum( weight / (k + rank(d)) )
        """
        import math
        import re
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        chunk_map: dict[UUID, RetrievedChunk] = {}
        rrf_scores: dict[UUID, float] = {}

        # Process vector results
        for rank, chunk in enumerate(vector_results, start=1):
            chunk_id = chunk.chunk_id
            rrf_score = self.vector_weight / (self.rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_score

            chunk_map[chunk_id] = RetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=0.0,
                vector_score=chunk.vector_score,
                keyword_score=None,
                source_url=chunk.source_url,
                department=chunk.department,
                owner=chunk.owner,
                last_verified=chunk.last_verified,
                token_count=chunk.token_count,
            )

        # Process keyword results
        for rank, chunk in enumerate(keyword_results, start=1):
            chunk_id = chunk.chunk_id
            rrf_score = self.keyword_weight / (self.rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_score

            if chunk_id in chunk_map:
                # Merge metadata and scores for duplicate item
                chunk_map[chunk_id].keyword_score = chunk.keyword_score
            else:
                chunk_map[chunk_id] = RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=0.0,
                    vector_score=None,
                    keyword_score=chunk.keyword_score,
                    source_url=chunk.source_url,
                    department=chunk.department,
                    owner=chunk.owner,
                    last_verified=chunk.last_verified,
                    token_count=chunk.token_count,
                )

        # Assign final fused RRF scores with soft entity boosts & recency decay (never hard WHERE)
        for chunk_id, fused_score in rrf_scores.items():
            chunk = chunk_map[chunk_id]
            multiplier = 1.0

            # 1. Soft department boost
            if target_departments and chunk.department:
                if any(dept.lower() in chunk.department.lower() for dept in target_departments):
                    multiplier *= dept_boost

            # 2. Soft semester boost
            if target_semesters and chunk.content:
                chunk_lower = chunk.content.lower()
                if any(sem.lower() in chunk_lower for sem in target_semesters):
                    multiplier *= 1.15

            # 3. Soft branch boost
            if target_branches and chunk.content:
                if any(
                    re.search(r"\b" + re.escape(b) + r"\b", chunk.content, re.IGNORECASE)
                    for b in target_branches
                ):
                    multiplier *= 1.20

            # 4. Soft recency decay boost (up to 20% boost for fresh circulars decaying over 180 days)
            if apply_recency and chunk.last_verified:
                try:
                    chk_dt = (
                        chunk.last_verified.replace(tzinfo=UTC)
                        if chunk.last_verified.tzinfo is None
                        else chunk.last_verified
                    )
                    age_days = max(0, (now - chk_dt).days)
                    recency_factor = math.exp(-0.693 * (age_days / 180.0))
                    multiplier *= 1.0 + 0.20 * recency_factor
                except Exception:
                    pass

            chunk.score = fused_score * multiplier

        # Sort descending by fused RRF score
        sorted_chunks = sorted(chunk_map.values(), key=lambda x: x.score, reverse=True)

        # Assign final merged rank and trim to top_k
        merged_results: list[RetrievedChunk] = []
        for rank, chunk in enumerate(sorted_chunks[:top_k], start=1):
            chunk.rank = rank
            merged_results.append(chunk)

        logger.debug(
            f"Merged {len(vector_results)} vector + {len(keyword_results)} keyword results "
            f"into {len(merged_results)} distinct chunks."
        )
        return merged_results

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 25,
        candidate_k: int | None = None,
        allowed_statuses: list[str] | None = None,
        departments: list[str] | None = None,
        include_superseded: bool = False,
    ) -> list[RetrievedChunk]:
        """Execute parallel hybrid search with domain NLP normalization and entity routing."""
        if not query.strip():
            return []

        effective_candidate_k = candidate_k if candidate_k is not None else max(40, top_k * 2)

        import re

        norm = query_normalizer.normalize(query)
        v_query = norm.expanded_vector or query
        k_query = norm.expanded_keyword or query

        # Detect historical notice query intent (e.g. "old timetable", "previous circular", "earlier schedule")
        is_historical = bool(
            re.search(
                r"\b(old|previous|earlier|past|historical|superseded|archive)\b",
                query,
                re.IGNORECASE,
            )
        )
        effective_superseded = include_superseded or is_historical

        # Target departments: explicit override or NLP-detected departments
        target_depts = (
            departments if departments is not None else (norm.detected_departments or None)
        )

        vector_results: list[RetrievedChunk] = []
        keyword_results: list[RetrievedChunk] = []

        # Phase 1b: Unconstrained candidate retrieval across corpus so college-wide circulars
        # and departmental notices are never missed. Department intent is applied as a soft
        # RRF ranking boost rather than a rigid SQL WHERE filter.
        vector_results = await self.vector_searcher.search(
            session=session,
            query=v_query,
            top_k=effective_candidate_k,
            allowed_statuses=allowed_statuses,
            departments=None,
            include_superseded=effective_superseded,
        )
        keyword_results = await self.keyword_searcher.search(
            session=session,
            query=k_query,
            top_k=effective_candidate_k,
            allowed_statuses=allowed_statuses,
            departments=None,
            include_superseded=effective_superseded,
        )

        # Detect query branches for soft ranking boost
        query_branches: list[str] = []
        for b in ["CSE", "IT", "ECE", "EE", "ME", "CE", "AUTO"]:
            if re.search(r"\b" + b + r"\b", query, re.IGNORECASE):
                query_branches.append(b)

        return self.reciprocal_rank_fusion(
            vector_results=vector_results,
            keyword_results=keyword_results,
            top_k=top_k,
            target_departments=target_depts,
            target_semesters=norm.detected_semesters or None,
            target_branches=query_branches or None,
            apply_recency=True,
        )
