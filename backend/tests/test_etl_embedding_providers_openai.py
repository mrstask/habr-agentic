"""Tests for the OpenAI embedding provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.etl.embedding.base import EmbeddingError, EmbeddingRequest, EmbeddingResult
from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider


def _make_mock_response(
    embedding: list[float] | None = None,
    prompt_tokens: int = 10,
    total_tokens: int = 10,
):
    """Create a mock OpenAI CreateEmbeddingResponse."""
    if embedding is None:
        embedding = [0.1, 0.2, 0.3]

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.total_tokens = total_tokens

    data_item = MagicMock()
    data_item.embedding = embedding

    response = MagicMock()
    response.data = [data_item]
    response.usage = usage
    return response


class TestOpenAIEmbeddingProviderInit:
    def test_default_values(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "text-embedding-3-small"
        assert provider.timeout == 120
        assert provider.max_retries == 3
        assert provider.dimensions is None
        assert provider.name == "openaiembedding"

    def test_custom_values(self):
        provider = OpenAIEmbeddingProvider(
            api_key="key",
            model="text-embedding-3-large",
            timeout=60,
            max_retries=5,
            dimensions=1024,
        )
        assert provider.model == "text-embedding-3-large"
        assert provider.timeout == 60
        assert provider.max_retries == 5
        assert provider.dimensions == 1024


class TestOpenAIEmbeddingProviderGetClient:
    def test_client_is_lazy(self):
        provider = OpenAIEmbeddingProvider(api_key="key")
        assert provider._client is None

    def test_client_is_cached(self):
        provider = OpenAIEmbeddingProvider(api_key="key")
        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            client1 = provider._get_client()
            client2 = provider._get_client()
            assert client1 is client2
            mock_cls.assert_called_once_with(api_key="key", timeout=120, max_retries=3)


class TestOpenAIEmbeddingProviderEmbed:
    @pytest.mark.asyncio
    async def test_embed_success(self):
        provider = OpenAIEmbeddingProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response(embedding=[0.1, 0.2, 0.3], prompt_tokens=10, total_tokens=10)

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.embed(EmbeddingRequest(text="hello world"))

        assert isinstance(result, EmbeddingResult)
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.provider_name == "openaiembedding"
        assert result.model_name == "text-embedding-3-small"
        assert result.dimensions == 3
        assert result.token_usage == {"input": 10, "total": 10}
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_embed_with_request_model_override(self):
        provider = OpenAIEmbeddingProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response(embedding=[0.1])

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.embed(EmbeddingRequest(text="text", model="text-embedding-3-large"))

            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert call_kwargs["model"] == "text-embedding-3-large"

    @pytest.mark.asyncio
    async def test_embed_with_dimensions(self):
        provider = OpenAIEmbeddingProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response(embedding=[0.1, 0.2])

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.embed(EmbeddingRequest(text="text", dimensions=256))

            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert call_kwargs["dimensions"] == 256

    @pytest.mark.asyncio
    async def test_embed_with_provider_dimensions(self):
        provider = OpenAIEmbeddingProvider(api_key="key", max_retries=1, dimensions=512)
        mock_response = _make_mock_response(embedding=[0.1])

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.embed(EmbeddingRequest(text="text"))

            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert call_kwargs["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_embed_raises_after_max_retries(self):
        provider = OpenAIEmbeddingProvider(api_key="key", max_retries=2)

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(side_effect=Exception("API error"))
            mock_cls.return_value = mock_client

            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(EmbeddingRequest(text="text"))

            assert "2 attempts" in str(exc_info.value)
            assert exc_info.value.provider == "openaiembedding"
            assert exc_info.value.retryable is True


class TestOpenAIEmbeddingProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        provider = OpenAIEmbeddingProvider(api_key="key")
        mock_response = _make_mock_response(embedding=[0.1])

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        provider = OpenAIEmbeddingProvider(api_key="key")

        with patch("app.etl.embedding.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(side_effect=Exception("unreachable"))
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is False
