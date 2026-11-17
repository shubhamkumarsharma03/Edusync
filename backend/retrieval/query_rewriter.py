"""Conversational Query Rewriter Module for EduSync.

Transforms conversational follow-up questions into standalone, fully context-resolved queries
for hybrid search and cross-encoder reranking.
"""

import json
import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from api.config import get_settings
from retrieval.http_client import get_http_client

logger = logging.getLogger(__name__)


class RewrittenQuery(BaseModel):
    standalone_query: str
    search_queries: list[str] = Field(default_factory=list)
    entities: dict[str, str | None] = Field(default_factory=dict)
    is_rewritten: bool = False


class ConversationalQueryRewriter:
    """Fast, single-call LLM query rewriter for multi-turn college student queries."""

    # Heuristic markers that signal the query likely depends on conversation context
    CONTEXT_DEPENDENT_MARKERS = {
        "it",
        "this",
        "that",
        "these",
        "those",
        "he",
        "she",
        "they",
        "them",
        "same",
        "also",
        "extended",
        "postponed",
        "cancelled",
        "fee",
        "fees",
        "last date",
        "deadline",
        "timing",
        "time",
        "where",
        "how much",
        "eligibility",
        "what about",
        "is it",
        "will it",
        "can i",
        "do i need",
        "kab",
        "kaha",
        "kitna",
        "aur",
        "bhi",
        "uska",
        "uski",
        "iske",
        "iski",
    }

    def __init__(self, model_name: str = "gemini-3.5-flash-lite") -> None:
        self.model_name = model_name
        self.settings = get_settings()

    def should_rewrite(self, query: str, history: Sequence[dict]) -> bool:
        """Heuristic check to bypass LLM call when query is already self-contained or history is empty."""
        if not history:
            return False

        words = set(re.findall(r"\b\w+\b", query.lower()))
        # If very short query with history (e.g. "what about fees?")
        if len(words) <= 6:
            return True
        # If contains pronouns or reference markers
        if any(marker in query.lower() for marker in self.CONTEXT_DEPENDENT_MARKERS):
            return True
        return False

    async def rewrite(self, query: str, history: Sequence[dict]) -> RewrittenQuery:
        """Rewrite conversational follow-up into a standalone query with explicit college context."""
        cleaned_query = query.strip()
        if not self.should_rewrite(cleaned_query, history):
            return RewrittenQuery(
                standalone_query=cleaned_query, search_queries=[cleaned_query], is_rewritten=False
            )

        api_key = self.settings.GEMINI_API_KEY
        if not api_key or api_key.startswith("mock"):
            return RewrittenQuery(
                standalone_query=cleaned_query, search_queries=[cleaned_query], is_rewritten=False
            )

        # Format recent history (up to last 4 turns)
        formatted_history = []
        for msg in list(history)[-4:]:
            role = msg.get("role", "user").capitalize()
            content = str(msg.get("content", ""))[:300]
            formatted_history.append(f"{role}: {content}")
        hist_text = "\n".join(formatted_history)

        prompt = f"""You are the Query Rewriting Engine for EduSync, the institutional AI assistant for Engineering College Ajmer (ECA).
A student is asking a follow-up question in an ongoing conversation.
Rewrite their question into a clear, completely self-contained, standalone question suitable for searching institutional college notices and circulars.

Strict Guidelines:
1. Resolve all ambiguous pronouns ("it", "they", "this exam", "the notice") using the conversation context.
2. Preserve specific details: semester (e.g. 3rd sem, 7th sem), course (B.Tech, MBA, MCA), department (CSE, Exam Section), and exam type (Mid-term, Practical, Back Exam).
3. If the user question is in Hindi/Hinglish (e.g. "kb tk bhr skte h?"), produce an accurate English standalone query with relevant terms.
4. Output STRICT JSON:
{{
  "standalone_query": "Fully resolved self-contained student question",
  "search_queries": ["1-3 specific keyword search phrases for notice retrieval"],
  "entities": {{"department": "...", "semester": "...", "category": "..."}}
}}

CONVERSATION HISTORY:
{hist_text}

STUDENT'S LATEST QUESTION:
{cleaned_query}

JSON:"""

        client = get_http_client()
        for model in [
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
        ]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.0,
                        "maxOutputTokens": 300,
                        "responseMimeType": "application/json",
                    },
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        raw_json = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                        try:
                            parsed = json.loads(raw_json)
                        except Exception:
                            m = re.search(r"\{[\s\S]*\}", raw_json)
                            parsed = json.loads(m.group(0)) if m else {}

                        if parsed and isinstance(parsed, dict):
                            standalone = parsed.get("standalone_query") or cleaned_query
                            search_qs = parsed.get("search_queries") or [standalone]
                            entities = parsed.get("entities") or {}
                            return RewrittenQuery(
                                standalone_query=standalone,
                                search_queries=search_qs,
                                entities=entities,
                                is_rewritten=(standalone.strip().lower() != cleaned_query.lower()),
                            )
                elif resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"Query rewriter {model} temporarily unavailable (HTTP {resp.status_code}), cascading..."
                    )
            except Exception as e:
                logger.warning(f"Query rewriter {model} failed: {e}")

        # Fallback to original query if LLM call fails
        return RewrittenQuery(
            standalone_query=cleaned_query, search_queries=[cleaned_query], is_rewritten=False
        )


query_rewriter = ConversationalQueryRewriter()
