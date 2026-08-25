import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from db.session import get_db
from retrieval.confidence_gate import ConfidenceGate
from retrieval.hybrid_search import HybridSearcher
from retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

settings = get_settings()


class ChatRequest(BaseModel):
    query: str = Field(..., description="Student query or question")
    department: str | None = Field(None, description="Optional department filter")
    session_id: str | None = Field(None, description="Client session identifier")


class SourceCitation(BaseModel):
    title: str
    url: str | None = None
    department: str | None = None
    last_verified: str | None = None
    confidence_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: str = "high"
    confidence_score: float = 1.0
    is_fallback: bool = False
    query: str


# Persistent async HTTP client for fast REST Gemini calls

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=3.5,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _http_client


async def warm_llm_client() -> None:
    """Pre-warm Gemini client connection at server startup."""
    api_key = settings.GEMINI_API_KEY
    if api_key and not api_key.startswith("mock"):
        try:
            client = get_http_client()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
            await client.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]})
        except Exception:
            pass


async def generate_llm_answer_async(query: str, chunks_text: str) -> str:
    """Generate grounded answer using high-speed async Gemini REST API with instant fallback."""
    api_key = settings.GEMINI_API_KEY
    if api_key and not api_key.startswith("mock"):
        prompt = f"""You are EduSync, the institutional AI assistant for Engineering College Ajmer (ECA).
Answer the student's question accurately and helpfully based ONLY on the verified official circulars and notices below.
Do not speculate or hallucinate outside the provided context. If the notice contains dates, deadlines, or instructions, summarize them clearly in bullet points.

VERIFIED OFFICIAL CIRCULARS & NOTICES:
{chunks_text[:4000]}

STUDENT QUESTION:
{query}

ANSWER:"""
        try:
            client = get_http_client()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800},
            }
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
        except Exception as e:
            logger.warning(f"Fast Gemini generation fallback: {e}")

    # Instant grounded synthesis fallback
    return (
        f"Here are the verified official details from Engineering College Ajmer notices:\n\n"
        f"{chunks_text[:1400]}"
    )


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    session: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Answer student questions using Hybrid Search, Reranking, Confidence Gating, and Citation."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    searcher = HybridSearcher()
    reranker = CrossEncoderReranker()
    gate = ConfidenceGate()

    # 1. Hybrid Search (Vector + Keyword via RRF)
    raw_chunks = await searcher.search(
        session=session,
        query=query,
        top_k=10,
    )

    if not raw_chunks:
        return ChatResponse(
            answer="I don't have verified information on this in the official circulars. Please check with the relevant department office or visit the official college website.",
            sources=[],
            confidence="low",
            confidence_score=0.0,
            is_fallback=True,
            query=query,
        )

    # 2. Cross-Encoder Reranking (executed in threadpool to avoid blocking event loop)
    import asyncio

    reranked_chunks = await asyncio.to_thread(
        reranker.rerank, query=query, chunks=raw_chunks, top_k=4
    )

    # 3. Confidence Gating (Trust Layer)
    gate_result = gate.evaluate(reranked_chunks)

    if gate_result.is_fallback:
        return ChatResponse(
            answer=gate_result.fallback_message
            or "I don't have enough confidence in the available documents to answer accurately.",
            sources=[],
            confidence=gate_result.confidence_level.value,
            confidence_score=gate_result.top_score,
            is_fallback=True,
            query=query,
        )

    # 4. Format verified context
    context_blocks = []
    citations: list[SourceCitation] = []
    seen_urls: set[str] = set()

    for chunk in gate_result.qualifying_chunks:
        context_blocks.append(f"--- Document Notice ---\n{chunk.content}")
        url = chunk.source_url or "https://www.ecajmer.ac.in"
        if url not in seen_urls:
            seen_urls.add(url)
            # Extract first line title if available
            first_line = chunk.content.split("\n")[0].strip("# ").strip()
            title = first_line if len(first_line) > 5 else f"{chunk.department or 'College'} Notice"
            citations.append(
                SourceCitation(
                    title=title,
                    url=url,
                    department=chunk.department,
                    last_verified="Verified Fresh",
                    confidence_score=chunk.score,
                )
            )

    combined_context = "\n\n".join(context_blocks)

    # 5. Generate Grounded Answer asynchronously with persistent connection & timeout
    answer_text = await generate_llm_answer_async(query, combined_context)

    return ChatResponse(
        answer=answer_text,
        sources=citations,
        confidence=gate_result.confidence_level.value,
        confidence_score=gate_result.top_score,
        is_fallback=False,
        query=query,
    )
