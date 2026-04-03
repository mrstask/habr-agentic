"""
Tests for the Ollama embedding provider.

Tests the happy path of generating embeddings via the Ollama API,
with mocked external calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider
from app.etl.embedding.base import EmbeddingRequest, EmbeddingResult


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx async client."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture
def provider():
    """Create an Ollama embedding provider for testing."""
    return OllamaEmbeddingProvider(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
        timeout=300,
        max_retries=3,
    )


@pytest.mark.asyncio
async def test_embed_success(provider, mock_httpx_client):
    """Test successful embedding generation."""
    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        result = await provider.embed(EmbeddingRequest(text="test text"))

    assert isinstance(result, EmbeddingResult)
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.provider_name == "ollamaembedding"
    assert result.model_name == "nomic-embed-text"
    assert result.dimensions == 3
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_embed_with_model_override(provider, mock_httpx_client):
    """Test embedding with model override."""
    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        result = await provider.embed(
            EmbeddingRequest(text="test", model="custom-model")
        )

    assert result.model_name == "custom-model"
    mock_httpx_client.post.assert_called_once()
    call_kwargs = mock_httpx_client.post.call_args[1]
    assert call_kwargs["json"]["model"] == "custom-model"


@pytest.mark.asyncio
async def test_embed_batch_success(provider, mock_httpx_client):
    """Test successful batch embedding."""
    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        results = await provider.embed_batch(["text1", "text2"])

    assert len(results) == 2
    assert all(isinstance(r, EmbeddingResult) for r in results)
    assert results[0].embedding == [0.1, 0.2, 0.3]
    assert results[1].embedding == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_batch_partial_failure(provider, mock_httpx_client):
    """Test batch embedding with partial failure."""
    def side_effect(*args, **kwargs):
        if kwargs.get("json", {}).get("prompt") == "text2":
            raise Exception("API error")
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}
        mock_response.raise_for_status = MagicMock()
        return mock_response

    mock_httpx_client.post.side_effect = side_effect

    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        results = await provider.embed_batch(["text1", "text2"])

    assert len(results) == 2
    assert results[0].embedding == [0.1, 0.2]
    assert results[1].error is not None


@pytest.mark.asyncio
async def test_health_check_success(provider, mock_httpx_client):
    """Test successful health check."""
    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        result = await provider.health_check()

    assert result is True
    mock_httpx_client.get.assert_called_once_with("/api/version")


@pytest.mark.asyncio
async def test_health_check_failure(provider, mock_httpx_client):
    """Test health check failure."""
    mock_httpx_client.get.side_effect = Exception("Connection refused")

    with patch.object(provider, "_get_client", return_value=mock_httpx_client):
        result = await provider.health_check()

    assert result is False


def test_is_retryable_error(provider):
    """Test retryable error detection."""
    assert provider._is_retryable_error(Exception("timeout occurred")) is True
    assert provider._is_retryable_error(Exception("connection refused")) is True
    assert provider._is_retryable_error(Exception("network error")) is True
    assert provider._is_retryable_error(Exception("invalid request")) is False
