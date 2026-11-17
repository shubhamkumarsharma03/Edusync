import logging
from collections.abc import Sequence
from urllib.parse import unquote, urlparse

from api.config import get_settings
from retrieval.schemas import GenerationResult, RetrievedChunk, SourceCitation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are EduSync, an intelligent institutional assistant for Engineering College Ajmer.
Your task is to answer student questions accurately and concisely based ONLY on the verified official document excerpts provided below.

Strict Guidelines:
1. Grounding: Answer exclusively using the verified context excerpts. Do NOT assume, extrapolate, or invent facts, dates, deadlines, or fees.
2. Missing Info: If the provided excerpts do not contain enough information to fully answer the question, clearly state what is known from the circulars and note that additional details should be verified with the department office.
3. Tone & Format: Be concise, clear, professional, and friendly to students. Use bullet points for schedules or multi-step instructions.
4. Do NOT manually format source links or footnotes in the text body; source citations are automatically rendered by the platform interface.
"""


class LLMGenerator:
    """Grounded LLM response generator with multi-provider fallback and citation extraction."""

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        primary_model: str = "claude-3-haiku-20240307",
        fallback_model: str = "gpt-4o-mini",
    ) -> None:
        settings = get_settings()
        self.anthropic_key = anthropic_api_key or settings.ANTHROPIC_API_KEY
        self.openai_key = openai_api_key or settings.OPENAI_API_KEY
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    @staticmethod
    def _format_document_title(url: str, department: str | None = None) -> str:
        """Derive a clean, readable document title from its URL and department."""
        try:
            parsed = urlparse(url)
            filename = unquote(parsed.path.split("/")[-1])
            if filename.endswith((".pdf", ".html", ".htm", ".csv", ".xlsx")):
                filename = filename.rsplit(".", 1)[0]
            clean_name = filename.replace("_", " ").replace("-", " ").strip().title()
            if department and clean_name:
                return f"{department} — {clean_name}"
            elif department:
                return f"{department} Circular"
            return clean_name or "Official Notice"
        except Exception:
            return f"{department} Notice" if department else "Official Notice"

    def extract_sources(self, chunks: Sequence[RetrievedChunk]) -> list[SourceCitation]:
        """Extract and deduplicate source citations from retrieved chunks."""
        citations: list[SourceCitation] = []
        seen_urls: set[str] = set()

        for chunk in chunks:
            if chunk.source_url and chunk.source_url not in seen_urls:
                seen_urls.add(chunk.source_url)
                doc_title = self._format_document_title(chunk.source_url, chunk.department)
                citations.append(
                    SourceCitation(
                        document=doc_title,
                        last_verified=chunk.last_verified,
                        url=chunk.source_url,
                    )
                )

        return citations

    def build_prompt(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        facts_context: str | None = None,
    ) -> tuple[str, str]:
        """Construct system and user prompts with structured context blocks and verified facts."""
        context_blocks: list[str] = []

        if facts_context:
            context_blocks.append(f"{facts_context}\n")

        for idx, chunk in enumerate(chunks, start=1):
            dept_str = f"Department: {chunk.department}" if chunk.department else "General"
            verified_str = (
                chunk.last_verified.strftime("%Y-%m-%d")
                if hasattr(chunk.last_verified, "strftime")
                else str(chunk.last_verified)
            )
            header = f"[Context #{idx} | {dept_str} | Verified: {verified_str}]"
            context_blocks.append(f"{header}\n{chunk.content.strip()}")

        context_text = "\n\n".join(context_blocks)
        user_prompt = (
            f"Official Document Excerpts:\n"
            f"----------------------------------------\n"
            f"{context_text}\n"
            f"----------------------------------------\n\n"
            f"Student Question: {query}\n\n"
            f"Answer:"
        )

        return SYSTEM_PROMPT, user_prompt

    async def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """Execute generation using Anthropic Claude API."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
        response = await client.messages.create(
            model=self.primary_model,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Extract response text
        content_blocks = response.content
        if content_blocks and hasattr(content_blocks[0], "text"):
            return getattr(content_blocks[0], "text", "").strip()
        return str(response.content).strip()

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Execute generation using OpenAI API as fallback."""
        import openai

        client = openai.AsyncOpenAI(api_key=self.openai_key)
        response = await client.chat.completions.create(
            model=self.fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return (content or "").strip()

    def _generate_offline_answer(self, query: str, chunks: Sequence[RetrievedChunk]) -> str:
        """Fallback grounded extractor when external API keys are unavailable (dev/offline mode)."""
        if not chunks:
            return (
                "I don't have verified information on this topic in the official college circulars or notices. "
                "Please check with the relevant department office."
            )
        # Construct factual direct summary from highest-ranked chunks
        points = [f"• {chunk.content.strip()}" for chunk in chunks[:3]]
        return "Based on the official circulars for your query:\n\n" + "\n\n".join(points)

    async def generate_answer(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        confidence: float = 0.0,
        facts_context: str | None = None,
    ) -> GenerationResult:
        """Generate a grounded response using available LLM providers with citation metadata.

        Args:
            query: The user's question.
            chunks: Qualifying retrieved document chunks passing confidence gate.
            confidence: Normalized confidence score from reranker.
            facts_context: Optional formatted key facts extracted from notice memory.

        Returns:
            GenerationResult containing answer text, source citations list, and confidence.
        """
        if not chunks:
            return GenerationResult(
                answer=(
                    "I don't have verified information on this in the official college circulars or notices. "
                    "Please check directly with the department office or college website."
                ),
                sources=[],
                confidence=0.0,
                is_fallback=True,
            )

        citations = self.extract_sources(chunks)
        system_prompt, user_prompt = self.build_prompt(query, chunks, facts_context=facts_context)

        answer_text: str | None = None

        # 1. Try Primary Provider (Anthropic Claude)
        if self.anthropic_key:
            try:
                logger.info(f"Generating answer using primary LLM ({self.primary_model})...")
                answer_text = await self._call_anthropic(system_prompt, user_prompt)
            except Exception as e:
                logger.warning(
                    f"Primary LLM provider (Anthropic) failed: {e}. Attempting fallback..."
                )

        # 2. Try Fallback Provider (OpenAI)
        if answer_text is None and self.openai_key:
            try:
                logger.info(f"Generating answer using fallback LLM ({self.fallback_model})...")
                answer_text = await self._call_openai(system_prompt, user_prompt)
            except Exception as e:
                logger.error(f"Fallback LLM provider (OpenAI) failed: {e}")

        # 3. If no LLM keys or network calls failed, use deterministic offline generator
        if answer_text is None:
            logger.info("Using offline grounded generator (no API keys or external calls failed).")
            answer_text = self._generate_offline_answer(query, chunks)

        return GenerationResult(
            answer=answer_text,
            sources=citations,
            confidence=round(confidence, 4),
            is_fallback=False,
        )
