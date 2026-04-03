"""
Tests for the OpenAI image generation provider.

Tests the happy path of generating images via the OpenAI DALL-E API,
with mocked external calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.etl.image_generation.providers.openai import OpenAIImageGenerationProvider
from app.etl.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI async client."""
    mock_client = MagicMock()
    mock_images = MagicMock()
    mock_images.generate = AsyncMock()
    mock_client.images = mock_images
    return mock_client


@pytest.fixture
def provider():
    """Create an OpenAI image generation provider for testing."""
    return OpenAIImageGenerationProvider(
        api_key="test-api-key",
        model="dall-e-3",
        timeout=120,
        max_retries=3,
    )


@pytest.mark.asyncio
async def test_generate_success(provider, mock_openai_client):
    """Test successful image generation."""
    mock_image_data = MagicMock()
    mock_image_data.url = "https://example.com/image.png"
    mock_image_data.b64_json = None
    mock_image_data.revised_prompt = "A beautiful landscape"

    mock_response = MagicMock()
    mock_response.data = [mock_image_data]
    mock_openai_client.images.generate.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.generate(
            ImageGenerationRequest(prompt="A beautiful landscape")
        )

    assert isinstance(result, ImageGenerationResult)
    assert result.image_url == "https://example.com/image.png"
    assert result.provider_name == "openaiimagegeneration"
    assert result.model_name == "dall-e-3"
    assert result.revised_prompt == "A beautiful landscape"
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_generate_with_model_override(provider, mock_openai_client):
    """Test image generation with model override."""
    mock_image_data = MagicMock()
    mock_image_data.url = "https://example.com/image.png"
    mock_image_data.b64_json = None
    mock_image_data.revised_prompt = None

    mock_response = MagicMock()
    mock_response.data = [mock_image_data]
    mock_openai_client.images.generate.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.generate(
            ImageGenerationRequest(prompt="test", model="dall-e-2")
        )

    assert result.model_name == "dall-e-2"
    mock_openai_client.images.generate.assert_called_once()
    call_kwargs = mock_openai_client.images.generate.call_args[1]
    assert call_kwargs["model"] == "dall-e-2"


@pytest.mark.asyncio
async def test_generate_with_b64_json(provider, mock_openai_client):
    """Test image generation returning base64 data."""
    mock_image_data = MagicMock()
    mock_image_data.url = None
    mock_image_data.b64_json = "base64encodeddata"
    mock_image_data.revised_prompt = None

    mock_response = MagicMock()
    mock_response.data = [mock_image_data]
    mock_openai_client.images.generate.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.generate(
            ImageGenerationRequest(prompt="test")
        )

    assert result.image_b64 == "base64encodeddata"
    assert result.image_url is None


@pytest.mark.asyncio
async def test_health_check_success(provider, mock_openai_client):
    """Test successful health check."""
    mock_image_data = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [mock_image_data]
    mock_openai_client.images.generate.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(provider, mock_openai_client):
    """Test health check failure."""
    mock_openai_client.images.generate.side_effect = Exception("API error")

    with patch.object(provider, "_get_client", return_value=mock_openai_client):
        result = await provider.health_check()

    assert result is False


def test_is_retryable_error(provider):
    """Test retryable error detection."""
    assert provider._is_retryable_error(Exception("timeout occurred")) is True
    assert provider._is_retryable_error(Exception("rate limit exceeded")) is True
    assert provider._is_retryable_error(Exception("connection refused")) is True
    assert provider._is_retryable_error(Exception("invalid request")) is False
