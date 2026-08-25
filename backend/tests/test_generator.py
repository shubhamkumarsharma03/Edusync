from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from retrieval.generator import LLMGenerator
from retrieval.schemas import RetrievedChunk


def create_sample_chunk(
    content: str = "B.Tech Semester 7 Mid-Term exams commence on Sept 15, 2026.",
    score: float = 0.88,
    source_url: str = "https://ecajmer.ac.in/notices/exam_schedule_sem7.pdf",
    department: str = "Examination",
) -> RetrievedChunk:
    """Helper to create dummy RetrievedChunk."""
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        score=score,
        rerank_score=score,
        source_url=source_url,
        last_verified=datetime.now(UTC),
        token_count=15,
        department=department,
    )


def test_format_document_title():
    """Test converting raw URL and department to human-readable title."""
    title1 = LLMGenerator._format_document_title(
        "https://ecajmer.ac.in/notices/exam_schedule_sem7.pdf", "Examination"
    )
    assert title1 == "Examination — Exam Schedule Sem7"

    title2 = LLMGenerator._format_document_title(
        "https://ecajmer.ac.in/fee_notice.html", "Accounts"
    )
    assert title2 == "Accounts — Fee Notice"

    title3 = LLMGenerator._format_document_title("https://ecajmer.ac.in/notices/syllabus.pdf", None)
    assert title3 == "Syllabus"


def test_extract_sources_deduplication():
    """Test extracting and deduplicating source citations from chunks."""
    generator = LLMGenerator()
    chunk1 = create_sample_chunk(
        source_url="https://ecajmer.ac.in/exam.pdf", department="Examination"
    )
    chunk2 = create_sample_chunk(
        source_url="https://ecajmer.ac.in/exam.pdf", department="Examination"
    )
    chunk3 = create_sample_chunk(source_url="https://ecajmer.ac.in/fee.pdf", department="Accounts")

    sources = generator.extract_sources([chunk1, chunk2, chunk3])

    assert len(sources) == 2
    assert sources[0].url == "https://ecajmer.ac.in/exam.pdf"
    assert sources[1].url == "https://ecajmer.ac.in/fee.pdf"
    assert "Examination" in sources[0].document
    assert "Accounts" in sources[1].document


def test_build_prompt():
    """Test constructing system and user prompts with context excerpts."""
    generator = LLMGenerator()
    chunk = create_sample_chunk(content="Tuition fees due on August 30, 2026.")

    system_prompt, user_prompt = generator.build_prompt("When is fee due?", [chunk])

    assert "EduSync" in system_prompt
    assert "Tuition fees due on August 30, 2026." in user_prompt
    assert "Student Question: When is fee due?" in user_prompt
    assert "Department: Examination" in user_prompt


@pytest.mark.asyncio
async def test_generate_answer_empty_chunks():
    """Test generator returns fallback structure when given empty chunks."""
    generator = LLMGenerator()
    result = await generator.generate_answer(query="What is the exam date?", chunks=[])

    assert result.is_fallback is True
    assert result.confidence == 0.0
    assert len(result.sources) == 0
    assert "I don't have verified information" in result.answer


@pytest.mark.asyncio
async def test_generate_answer_offline_fallback():
    """Test generator falls back to deterministic summary when no API keys are provided."""
    generator = LLMGenerator(anthropic_api_key=None, openai_api_key=None)
    chunk = create_sample_chunk(content="Mid-term exams start Sept 15, 2026.")

    result = await generator.generate_answer(
        query="When do exams start?",
        chunks=[chunk],
        confidence=0.92,
    )

    assert result.is_fallback is False
    assert result.confidence == 0.92
    assert len(result.sources) == 1
    assert "Mid-term exams start Sept 15, 2026." in result.answer


@pytest.mark.asyncio
async def test_generate_answer_anthropic_primary():
    """Test successful generation using primary provider (Anthropic Claude)."""
    generator = LLMGenerator(anthropic_api_key="mock-key-123")
    chunk = create_sample_chunk()

    mock_text_block = MagicMock()
    mock_text_block.text = "Mid-term examinations will begin on September 15, 2026."
    mock_response = MagicMock(content=[mock_text_block])

    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic_cls.return_value = mock_client

        result = await generator.generate_answer(
            query="When are mid-term exams?",
            chunks=[chunk],
            confidence=0.88,
        )

        assert result.answer == "Mid-term examinations will begin on September 15, 2026."
        assert len(result.sources) == 1
        assert result.confidence == 0.88
        assert result.is_fallback is False
        mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_answer_openai_fallback():
    """Test automatic fallback to OpenAI when Anthropic primary provider fails."""
    generator = LLMGenerator(
        anthropic_api_key="mock-anthropic-key", openai_api_key="mock-openai-key"
    )
    chunk = create_sample_chunk()

    # Mock OpenAI response
    mock_choice = MagicMock()
    mock_choice.message.content = "OpenAI fallback: Mid-term exams start Sept 15, 2026."
    mock_openai_resp = MagicMock(choices=[mock_choice])

    with (
        patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
        patch("openai.AsyncOpenAI") as mock_openai_cls,
    ):
        # Anthropic raises an API error
        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=Exception("Anthropic API rate limited")
        )
        mock_anthropic_cls.return_value = mock_anthropic_client

        # OpenAI succeeds
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_openai_resp)
        mock_openai_cls.return_value = mock_openai_client

        result = await generator.generate_answer(
            query="When are mid-term exams?",
            chunks=[chunk],
            confidence=0.85,
        )

        assert "OpenAI fallback" in result.answer
        assert len(result.sources) == 1
        assert result.confidence == 0.85
        mock_anthropic_client.messages.create.assert_awaited_once()
        mock_openai_client.chat.completions.create.assert_awaited_once()
