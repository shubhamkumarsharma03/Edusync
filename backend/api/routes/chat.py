import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from db.session import get_db
from retrieval.confidence_gate import ConfidenceGate
from retrieval.fact_lookup import FactLookup
from retrieval.http_client import get_http_client
from retrieval.hybrid_search import HybridSearcher
from retrieval.query_rewriter import query_rewriter
from retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/chat", tags=["Chat"])

settings = get_settings()


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    query: str = Field(..., description="Student query or question")
    department: str | None = Field(None, description="Optional department filter")
    session_id: str | None = Field(None, description="Client session identifier")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Recent conversation turns"
    )


class SourceCitation(BaseModel):
    title: str
    url: str | None = None
    department: str | None = None
    last_verified: str | None = None
    confidence_score: float | None = None


class GroundedAnswerResult(BaseModel):
    answer: str
    answerable: bool = True
    evidence: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: str = "high"
    confidence_score: float = 1.0
    is_fallback: bool = False
    query: str


async def warm_llm_client() -> None:
    """Pre-warm Gemini client connection at server startup."""
    api_key = settings.GEMINI_API_KEY
    if api_key and not api_key.startswith("mock"):
        try:
            client = get_http_client()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
            await client.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]})
        except Exception:
            pass


async def generate_llm_answer_async(query: str, chunks_text: str) -> GroundedAnswerResult:
    """Generate grounded answer using high-speed async Gemini REST API with in-prompt evidence check."""
    api_key = settings.GEMINI_API_KEY
    if api_key and not api_key.startswith("mock"):
        prompt = f"""You are EduSync, the official AI assistant for Engineering College Ajmer (ECA).
Analyze whether the provided verified official notices contain direct, verified factual evidence to answer the student's question.

CRITICAL INSTRUCTIONS:
1. Grounding: Answer ONLY based on verified facts in the notices below.
2. Near-Miss Check: If the notices mention related topics (e.g. general exam fees, general circulars, or workshop announcements) but DO NOT contain the specific fact or answer requested by the student (e.g. duplicate degree fee or laptop requirements), you MUST set "answerable": false, "evidence": "", and "answer": "". DO NOT invent or extrapolate answers.
3. If "answerable": true, provide a clear, concise, professional markdown answer with bold dates, fees, and bullet points.
   - If the notice contains timetable tables or OCR LaTeX markup (e.g. \\begin{{tabular}}), ALWAYS convert them into a clean, human-readable markdown table. NEVER output raw LaTeX syntax.
   - Do NOT output raw metadata tags like "[Document Notice]".
4. Return STRICT JSON with keys:
{{
  "answerable": true or false,
  "evidence": "exact quote from notices supporting the answer, or empty string if not found",
  "answer": "markdown answer string, or empty string if unanswerable"
}}

VERIFIED OFFICIAL NOTICES:
{chunks_text[:4000]}

STUDENT QUESTION:
{query}

JSON RESPONSE:"""
        client = get_http_client()
        for model in [
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
        ]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 3000,
                        "responseMimeType": "application/json",
                    },
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        raw_text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                        try:
                            parsed = json.loads(raw_text)
                        except Exception:
                            m = re.search(r"\{[\s\S]*\}", raw_text)
                            parsed = json.loads(m.group(0)) if m else {}

                        if parsed and isinstance(parsed, dict):
                            is_ans = bool(parsed.get("answerable", True))
                            evidence_str = str(parsed.get("evidence") or "").strip()
                            ans_str = str(parsed.get("answer") or "").strip()
                            if not is_ans:
                                return GroundedAnswerResult(
                                    answerable=False, evidence="", answer=""
                                )
                            if ans_str:
                                return GroundedAnswerResult(
                                    answerable=True, evidence=evidence_str, answer=ans_str
                                )
                        elif raw_text:
                            return GroundedAnswerResult(
                                answerable=True, evidence="", answer=raw_text
                            )
                elif resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"Gemini model {model} temporarily unavailable (HTTP {resp.status_code}), trying next candidate..."
                    )
            except Exception as e:
                logger.warning(f"Fast Gemini generation ({model}) fallback: {e}")

    # Clean grounded synthesis fallback if LLM is unavailable
    cleaned_chunks = (
        chunks_text.replace("--- Document Notice ---", "").replace("[Document Notice]", "").strip()
    )
    fallback_text = (
        f"Here are the verified official details from Engineering College Ajmer notices:\n\n"
        f"{cleaned_chunks[:1400]}"
    )
    return GroundedAnswerResult(answer=fallback_text, answerable=True, evidence="fallback")


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

    # 0. Conversational Query Rewriting (Phase 3 Multi-Turn Context Resolution)
    search_query = query
    if req.history:
        history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
        rewritten = await query_rewriter.rewrite(query=query, history=history_dicts)
        if rewritten.is_rewritten:
            search_query = rewritten.standalone_query
            logger.info(f"Conversational query rewritten: '{query}' -> '{search_query}'")

    # 0b. Fast-path Fact Lookup from active notice memory
    matched_facts = await FactLookup.search(session=session, query=search_query, limit=5)
    if matched_facts and matched_facts[0].confidence >= 0.9:
        logger.info(f"Fast-path fact match found (confidence={matched_facts[0].confidence:.2f})")
        facts_context = FactLookup.format_facts_context(matched_facts)
        fast_res = await generate_llm_answer_async(search_query, facts_context)
        fast_answer = fast_res.answer if fast_res.answerable else ""
        if not fast_answer:
            fast_answer = facts_context[:1000]
        fact_sources = [
            SourceCitation(
                title=f.notice_title,
                url=f.source_url,
                department=None,
                last_verified="Verified Fresh",
                confidence_score=f.confidence,
            )
            for f in matched_facts[:2]
        ]
        return ChatResponse(
            answer=fast_answer,
            sources=fact_sources,
            confidence="high",
            confidence_score=matched_facts[0].confidence,
            is_fallback=False,
            query=query,
        )

    # 1. Hybrid Search (Vector + Keyword via RRF) to fetch top candidate pool
    raw_chunks = await searcher.search(
        session=session,
        query=search_query,
        top_k=20,
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

    # 2. Cross-Encoder / Jina Reranking to select top 5 most relevant chunks (natural query for cross-attention)
    reranked_chunks = await reranker.arerank(
        query=search_query,
        chunks=raw_chunks,
        top_k=5,
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
    if matched_facts:
        context_blocks.append(FactLookup.format_facts_context(matched_facts))

    citations: list[SourceCitation] = []
    seen_urls: set[str] = set()

    for chunk in gate_result.qualifying_chunks:
        context_blocks.append(chunk.content.strip())
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

    # 5. Generate Grounded Answer asynchronously with in-prompt evidence check
    llm_res = await generate_llm_answer_async(search_query, combined_context)
    if not llm_res.answerable:
        logger.info(
            f"Gemini in-prompt evidence check determined question is unanswerable from context: {query}"
        )
        return ChatResponse(
            answer=gate_result.fallback_message or gate.fallback_response(),
            sources=[],
            confidence="low",
            confidence_score=gate_result.top_score,
            is_fallback=True,
            query=query,
        )

    answer_text = llm_res.answer or gate.fallback_response()
    if gate_result.caveat:
        answer_text = f"{answer_text}\n\n> ⚠️ *{gate_result.caveat}*"

    return ChatResponse(
        answer=answer_text,
        sources=citations,
        confidence=gate_result.confidence_level.value,
        confidence_score=gate_result.top_score,
        is_fallback=False,
        query=query,
    )
