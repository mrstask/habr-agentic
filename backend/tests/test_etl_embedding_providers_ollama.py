"""Tests for the Ollama embedding provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.etl.embedding.base import EmbeddingError, EmbeddingRequest, EmbeddingResult
from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider


class TestOllamaEmbeddingProviderInit:
    def test_default_values(self):
        provider = OllamaEmbeddingProvider()
        assert provider.api_key is None
        assert provider.model == "nomic-embed-text"
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 300
        assert provider.max_retries == 3
        assert provider.name == "ollamaembedding"

    def test_custom_values(self):
        provider = OllamaEmbeddingProvider(
            model="custom-model",
            base_url="http://custom:1234",
            timeout=60,
            max_retries=5,
        )
        assert provider.model == "custom-model"
        assert provider.base_url == "http://custom:1234"
        assert provider.timeout == 60
        assert provider.max_retries == 5


class TestOllamaEmbeddingProviderGetClient:
    def test_client_is_lazy(self):
        provider = OllamaEmbeddingProvider()
        assert provider._client is None

    def test_client_is_cached(self):
        provider = OllamaEmbeddingProvider()
        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            client1 = provider._get_client()
            client2 = provider._get_client()
            assert client1 is client2
            mock_cls.assert_called_once_with(
                base_url="http://localhost:11434",
                timeout=300,
            )


class TestOllamaEmbeddingProviderEmbed:
    @pytest.mark.asyncio
    async def test_embed_success(self):
        provider = OllamaEmbeddingProvider(max_retries=1)
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.embed(EmbeddingRequest(text="hello world"))

        assert isinstance(result, EmbeddingResult)
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.provider_name == "ollamaembedding"
        assert result.model_name == "nomic-embed-text"
        assert result.dimensions == 3
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_embed_with_request_model_override(self):
        provider = OllamaEmbeddingProvider(max_retries=1)
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.embed(EmbeddingRequest(text="text", model="custom-model"))

            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_embed_raises_after_max_retries(self):
        provider = OllamaEmbeddingProvider(max_retries=2)

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("API error"))
            mock_cls.return_value = mock_client

            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(EmbeddingRequest(text="text"))

            assert "2 attempts" in str(exc_info.value)
            assert exc_info.value.provider == "ollamaembedding"
            assert exc_info.value.retryable is True


class TestOllamaEmbeddingProviderEmbedBatch:
    @pytest.mark.asyncio
    async def test_embed_batch_success(self):
        provider = OllamaEmbeddingProvider(max_retries=1)
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            results = await provider.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert all(isinstance(r, EmbeddingResult) for r in results)
        assert results[0].embedding == [0.1, 0.2]
        assert results[1].embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embed_batch_partial_failure(self):
        provider = OllamaEmbeddingProvider(max_retries=1)
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            # First call succeeds, second fails
            mock_client.post = AsyncMock(side_effect=[mock_response, Exception("fail")])
            mock_cls.return_value = mock_client

            results = await provider.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert results[0].embedding == [0.1, 0.2]
        assert results[1].embedding == []
        assert results[1].error is not None


class TestOllamaEmbeddingProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        provider = OllamaEmbeddingProvider()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        provider = OllamaEmbeddingProvider()

        with patch("app.etl.embedding.providers.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("unreachable"))
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is False
