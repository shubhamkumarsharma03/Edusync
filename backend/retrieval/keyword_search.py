import logging
import re
from collections.abc import Sequence
from typing import Any

from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.chunk import Chunk
from models.department import Department
from models.document import Document
from models.notice_memory import NoticeMemory
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


# Configurable college vocabulary and colloquial synonym mapping
COLLEGE_GLOSSARY: dict[str, str] = {
    r"\bsem\b": "semester",
    r"\bfine\b": "late fee fine",
    r"\b(bharna|bhrna|bharne)\b": "fill submit form",
    r"\b(kb tk|kab tak)\b": "last date deadline",
    r"\b(kitna|kitni)\b": "fee amount",
    r"\bclb\b": "club",
    r"\bwrkshop\b": "workshop",
    r"\bvanue\b": "venue",
    r"\bresheduled?\b": "reschedule rescheduled",
    r"\bpractcal\b": "practical",
    r"\bexamintion\b": "examination",
    r"\btarikh\b": "date",
    r"\btimetable\b": "schedule timetable",
    r"\bmidterm\b": "mid term",
}

# Stop words to ignore during OR-style FTS assembly
HINDI_ENGLISH_STOPWORDS: set[str] = {
    "ki",
    "ka",
    "ke",
    "hai",
    "hain",
    "aur",
    "kya",
    "me",
    "mein",
    "h",
    "se",
    "ko",
    "par",
    "tha",
    "the",
    "aaya",
    "aayi",
    "is",
    "for",
    "of",
    "in",
    "and",
    "or",
    "to",
    "what",
    "when",
    "where",
    "how",
    "who",
}


class KeywordSearcher:
    """Performs keyword search using PostgreSQL Full-Text Search (FTS) with stored tsvector,
    simple dictionary matching, OR-style ranking, and pg_trgm fuzzy matching for typos.
    """

    @classmethod
    def expand_with_glossary(cls, query: str) -> str:
        """Expand college slang, abbreviations, and Hinglish phrases using the domain glossary."""
        expanded = query
        for pattern, replacement in COLLEGE_GLOSSARY.items():
            expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)
        return expanded

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
        include_superseded: bool = False,
    ) -> list[RetrievedChunk]:
        """Execute database-backed full text keyword search against chunks.

        Uses stored generated `Chunk.tsv` column (GIN indexed, simple dictionary) with OR-ranked
        disjunction and fallback trigram fuzzy matching for unmatched typos.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        allowed = allowed_statuses if allowed_statuses is not None else ["fresh"]

        # 1. Expand query terms using college glossary
        expanded = self.expand_with_glossary(cleaned_query)

        # 2. Extract distinct alphanumeric tokens, filtering stopwords
        tokens = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9]+", expanded.lower())))
        fts_terms = [t for t in tokens if len(t) > 1 and t not in HINDI_ENGLISH_STOPWORDS]

        if not fts_terms:
            fts_terms = [t for t in tokens if len(t) > 1]

        if not fts_terms:
            return []

        # Construct OR-style ranked tsquery using 'simple' configuration
        or_query_str = " | ".join(fts_terms)
        tsquery = func.to_tsquery("simple", or_query_str)
        rank_expr = func.ts_rank_cd(Chunk.tsv, tsquery).label("rank_score")

        base_conditions = [
            Document.status.in_(allowed),
            Chunk.tsv.op("@@")(tsquery),
        ]
        if not include_superseded:
            base_conditions.append(
                (NoticeMemory.id.is_(None)) | (NoticeMemory.is_latest == True)  # noqa: E712
            )
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
            .outerjoin(NoticeMemory, Chunk.document_id == NoticeMemory.document_id)
            .where(*base_conditions)
            .order_by(rank_expr.desc())
            .limit(top_k)
        )

        rows: list[Any] = list((await session.execute(stmt)).all())

        # 3. Trigram Fuzzy Fallback (pg_trgm): If FTS yielded fewer than 3 hits, search via word_similarity
        if len(rows) == 0 and len(fts_terms) > 0:
            existing_ids = {r.id for r in rows}
            # Pick salient tokens (length >= 4) for fuzzy matching
            salient_terms = [t for t in fts_terms if len(t) >= 4][:3]
            for term in salient_terms:
                sim_expr = func.word_similarity(term, Chunk.content).label("sim_score")
                fuzzy_conditions = [
                    Document.status.in_(allowed),
                    sim_expr > 0.45,
                ]
                if existing_ids:
                    fuzzy_conditions.append(Chunk.id.not_in(existing_ids))

                fuzzy_stmt = (
                    select(
                        Chunk.id,
                        Chunk.document_id,
                        Chunk.content,
                        Chunk.token_count,
                        Chunk.last_verified,
                        Document.source_url,
                        Department.name.label("department"),
                        Document.owner,
                        sim_expr,
                    )
                    .join(Document, Chunk.document_id == Document.id)
                    .outerjoin(Department, Document.department_id == Department.id)
                    .outerjoin(NoticeMemory, Chunk.document_id == NoticeMemory.document_id)
                    .where(*fuzzy_conditions)
                    .order_by(sim_expr.desc())
                    .limit(top_k - len(rows))
                )
                fuzzy_rows = (await session.execute(fuzzy_stmt)).all()
                for fr in fuzzy_rows:
                    if fr.id not in existing_ids:
                        existing_ids.add(fr.id)
                        rows.append(fr)
                if len(rows) >= top_k:
                    break

        retrieved_chunks: list[RetrievedChunk] = []
        for rank, row in enumerate(rows[:top_k], start=1):
            score = float(getattr(row, "rank_score", getattr(row, "sim_score", 0.0)) or 0.0)
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
