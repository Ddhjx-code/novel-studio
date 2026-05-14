"""Tests for embedding adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.vectorstore.embedding import (
    EmbeddingConfig,
    OllamaEmbeddingAdapter,
    OpenAICompatEmbeddingAdapter,
    create_embedding_adapter,
)


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "http://test"),
    )


@pytest.fixture
def openai_adapter():
    return OpenAICompatEmbeddingAdapter(
        api_key="test-key", base_url="http://localhost:8000", model="text-embedding-3-small"
    )


@pytest.fixture
def ollama_adapter():
    return OllamaEmbeddingAdapter(base_url="http://localhost:11434", model="nomic-embed-text")


class TestOpenAICompatAdapter:
    @pytest.mark.asyncio
    async def test_embed_documents(self, openai_adapter):
        mock_resp = _mock_response({
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
            ]
        })
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await openai_adapter.embed_documents(["hello", "world"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @pytest.mark.asyncio
    async def test_embed_query(self, openai_adapter):
        mock_resp = _mock_response({"data": [{"index": 0, "embedding": [1.0, 2.0]}]})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await openai_adapter.embed_query("test query")
        assert result == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_empty_input(self, openai_adapter):
        result = await openai_adapter.embed_documents([])
        assert result == []

    def test_endpoint_adds_v1(self):
        adapter = OpenAICompatEmbeddingAdapter(
            api_key="k", base_url="http://example.com", model="m"
        )
        assert adapter._endpoint() == "http://example.com/v1/embeddings"

    def test_endpoint_preserves_v1(self):
        adapter = OpenAICompatEmbeddingAdapter(
            api_key="k", base_url="http://example.com/v1", model="m"
        )
        assert adapter._endpoint() == "http://example.com/v1/embeddings"

    def test_strips_trailing_slash(self):
        adapter = OpenAICompatEmbeddingAdapter(
            api_key="k", base_url="http://example.com/v1/", model="m"
        )
        assert adapter._endpoint() == "http://example.com/v1/embeddings"

    @pytest.mark.asyncio
    async def test_http_error_raises(self, openai_adapter):
        mock_resp = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "http://localhost:8000/v1/embeddings"),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                await openai_adapter.embed_documents(["test"])


class TestOllamaAdapter:
    @pytest.mark.asyncio
    async def test_embed_documents(self, ollama_adapter):
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response({"embedding": [0.1 * call_count, 0.2, 0.3]})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await ollama_adapter.embed_documents(["hello", "world"])
        assert len(result) == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_empty_input(self, ollama_adapter):
        result = await ollama_adapter.embed_documents([])
        assert result == []


class TestFactory:
    def test_creates_openai_adapter(self):
        config = EmbeddingConfig(
            api_format="openai_compat", base_url="http://x", model="m", api_key="k"
        )
        adapter = create_embedding_adapter(config)
        assert isinstance(adapter, OpenAICompatEmbeddingAdapter)

    def test_creates_ollama_adapter(self):
        config = EmbeddingConfig(api_format="ollama", base_url="http://x", model="m")
        adapter = create_embedding_adapter(config)
        assert isinstance(adapter, OllamaEmbeddingAdapter)

    def test_defaults_to_openai(self):
        config = EmbeddingConfig(api_format="unknown", base_url="http://x", model="m")
        adapter = create_embedding_adapter(config)
        assert isinstance(adapter, OpenAICompatEmbeddingAdapter)
