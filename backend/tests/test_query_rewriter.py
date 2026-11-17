from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from retrieval.query_rewriter import ConversationalQueryRewriter


def test_should_rewrite_empty_history():
    rewriter = ConversationalQueryRewriter()
    assert not rewriter.should_rewrite("When are the exams?", [])


def test_should_rewrite_with_pronouns():
    rewriter = ConversationalQueryRewriter()
    history = [{"role": "user", "content": "When is the 7th sem practical exam?"}]
    assert rewriter.should_rewrite("Is it extended?", history)
    assert rewriter.should_rewrite("What is the fee for that?", history)
    assert rewriter.should_rewrite("aur late fee kitna lagega?", history)


def test_should_rewrite_short_query():
    rewriter = ConversationalQueryRewriter()
    history = [{"role": "user", "content": "When is the 7th sem practical exam?"}]
    assert rewriter.should_rewrite("dates?", history)
    assert rewriter.should_rewrite("what about fees?", history)


@pytest.mark.asyncio
async def test_rewrite_fallback_on_unconfigured_api():
    with patch("retrieval.query_rewriter.get_settings") as mock_settings:
        mock_settings.return_value.GEMINI_API_KEY = "mock_key"
        rewriter = ConversationalQueryRewriter()
        res = await rewriter.rewrite(
            "Is it extended?", [{"role": "user", "content": "Notice for 3rd sem exam"}]
        )
        assert res.standalone_query == "Is it extended?"
        assert not res.is_rewritten


@pytest.mark.asyncio
async def test_rewrite_success():
    rewriter = ConversationalQueryRewriter()
    mock_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"standalone_query": "Has the B.Tech 3rd semester exam form submission deadline been extended?", "search_queries": ["B.Tech 3rd sem exam form extension"], "entities": {"semester": "3rd Sem", "category": "exam"}}'
                        }
                    ]
                }
            }
        ]
    }

    mock_client = AsyncMock()
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = mock_resp
    mock_client.post.return_value = mock_http_resp

    with (
        patch("retrieval.query_rewriter.get_http_client", return_value=mock_client),
        patch.object(rewriter.settings, "GEMINI_API_KEY", "valid_key"),
    ):
        res = await rewriter.rewrite(
            "Is it extended?",
            [
                {"role": "user", "content": "When is the B.Tech 3rd sem exam form last date?"},
                {"role": "assistant", "content": "The last date is 01.11.2026."},
            ],
        )
        assert res.is_rewritten
        assert "B.Tech 3rd semester" in res.standalone_query
        assert "extension" in res.search_queries[0]
