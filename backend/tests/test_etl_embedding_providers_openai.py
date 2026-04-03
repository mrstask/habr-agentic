"""
Tests for the OpenAI embedding provider.

Tests the happy path of generating embeddings via the OpenAI API,
with mocked external calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider
from app.etl.embedding.base import EmbeddingRequest, EmbeddingResult


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI async client."""
    mock_client = MagicMock()
    mock_embeddings = MagicMock()
    mock_embeddings.create = AsyncMock()
    mock_client.embeddings = mock_embeddings
    return mock_client


@pytest.fixture
def provider():
    """Create an OpenAI embedding provider for testing."""
    return OpenAIEmbeddingProvider(
        api_key="test-api-key",
        model="text-embedding-3-small",
        timeout=120,
        max_retries=3,
    )


@pytest.mark.asyncio
async def test_embed_success(provider, mock_openai_client):
    """Test successful embedding generation."""
    # Mock the response
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    mock_response.usage = MagicMock(prompt_tokens=10, total_tokens=10)
    mock_openai_client.embeddings.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.embed(EmbeddingRequest(text="test text"))

    assert isinstance(result, EmbeddingResult)
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.provider_name == "openaiembedding"
    assert result.model_name == "text-embedding-3-small"
    assert result.dimensions == 3
    assert result.token_usage == {"input": 10, "total": 10}
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_embed_with_model_override(provider, mock_openai_client):
    """Test embedding with model override."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2])]
    mock_response.usage = None
    mock_openai_client.embeddings.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.embed(
            EmbeddingRequest(text="test", model="text-embedding-3-large")
        )

    assert result.model_name == "text-embedding-3-large"
    mock_openai_client.embeddings.create.assert_called_once()
    call_kwargs = mock_openai_client.embeddings.create.call_args[1]
    assert call_kwargs["model"] == "text-embedding-3-large"


@pytest.mark.asyncio
async def test_embed_with_dimensions(provider, mock_openai_client):
    """Test embedding with dimensions parameter."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 512)]
    mock_response.usage = None
    mock_openai_client.embeddings.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.embed(
            EmbeddingRequest(text="test", dimensions=512)
        )

    assert result.dimensions == 512
    call_kwargs = mock_openai_client.embeddings.create.call_args[1]
    assert call_kwargs["dimensions"] == 512


@pytest.mark.asyncio
async def test_embed_batch_success(provider, mock_openai_client):
    """Test successful batch embedding."""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1, 0.2]),
        MagicMock(embedding=[0.3, 0.4]),
    ]
    mock_response.usage = MagicMock(prompt_tokens=20, total_tokens=20)
    mock_openai_client.embeddings.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        results = await provider.embed_batch(["text1", "text2"])

    assert len(results) == 2
    assert all(isinstance(r, EmbeddingResult) for r in results)
    assert results[0].embedding == [0.1, 0.2]
    assert results[1].embedding == [0.3, 0.4]


@pytest.mark.asyncio
async def test_health_check_success(provider, mock_openai_client):
    """Test successful health check."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock()]
    mock_openai_client.embeddings.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(provider, mock_openai_client):
    """Test health check failure."""
    mock_openai_client.embeddings.create.side_effect = Exception("API error")

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.health_check()

    assert result is False


def test_is_retryable_error(provider):
    """Test retryable error detection."""
    assert provider._is_retryable_error(Exception("timeout occurred")) is True
    assert provider._is_retryable_error(Exception("rate limit exceeded")) is True
    assert provider._is_retryable_error(Exception("connection refused")) is True
    assert provider._is_retryable_error(Exception("invalid request")) is False
