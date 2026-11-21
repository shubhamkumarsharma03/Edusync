import pytest

from retrieval.resembled_questions import get_closely_resembled_questions


@pytest.mark.asyncio
async def test_resembled_questions_matching_exam():
    """Test that query mentioning exam returns relevant exam questions."""
    suggestions = await get_closely_resembled_questions(
        "when is the exam scheduled?", "Examination"
    )
    assert len(suggestions) >= 2
    assert any("exam" in s.lower() for s in suggestions)


@pytest.mark.asyncio
async def test_resembled_questions_matching_fee():
    """Test that query mentioning fee returns relevant fee questions."""
    suggestions = await get_closely_resembled_questions("how to pay semester fees?")
    assert len(suggestions) >= 2
    assert any("fee" in s.lower() or "challan" in s.lower() for s in suggestions)


@pytest.mark.asyncio
async def test_resembled_questions_matching_mca():
    """Test that query mentioning MCA or department MCA returns MCA questions."""
    suggestions = await get_closely_resembled_questions("project guidelines", "MCA")
    assert len(suggestions) >= 2
    assert any("mca" in s.lower() or "project" in s.lower() for s in suggestions)


@pytest.mark.asyncio
async def test_resembled_questions_unrelated_query_fallback():
    """Test that completely unrelated query still provides useful institutional questions."""
    suggestions = await get_closely_resembled_questions("xyzqwerty nonexistent question")
    assert len(suggestions) >= 3
    assert any(
        "exam" in s.lower() or "fee" in s.lower() or "library" in s.lower() for s in suggestions
    )
