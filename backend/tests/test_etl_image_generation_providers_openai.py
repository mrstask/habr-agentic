"""Tests for the OpenAI image generation provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.etl.image_generation.base import (
    ImageGenerationError,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from app.etl.image_generation.providers.openai import OpenAIImageGenerationProvider


def _make_mock_response(
    url: str = "https://example.com/image.png",
    b64_json: str | None = None,
    revised_prompt: str | None = None,
):
    """Create a mock OpenAI ImagesResponse."""
    image_data = MagicMock()
    image_data.url = url
    image_data.b64_json = b64_json
    image_data.revised_prompt = revised_prompt

    response = MagicMock()
    response.data = [image_data]
    return response


class TestOpenAIImageGenerationProviderInit:
    def test_default_values(self):
        provider = OpenAIImageGenerationProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "dall-e-3"
        assert provider.timeout == 120
        assert provider.max_retries == 3
        assert provider.name == "openaiimagegeneration"

    def test_custom_values(self):
        provider = OpenAIImageGenerationProvider(
            api_key="key", model="dall-e-2", timeout=60, max_retries=5
        )
        assert provider.model == "dall-e-2"
        assert provider.timeout == 60
        assert provider.max_retries == 5


class TestOpenAIImageGenerationProviderGetClient:
    def test_client_is_lazy(self):
        provider = OpenAIImageGenerationProvider(api_key="key")
        assert provider._client is None

    def test_client_is_cached(self):
        provider = OpenAIImageGenerationProvider(api_key="key")
        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            client1 = provider._get_client()
            client2 = provider._get_client()
            assert client1 is client2
            mock_cls.assert_called_once_with(api_key="key", timeout=120, max_retries=3)


class TestOpenAIImageGenerationProviderGenerate:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        provider = OpenAIImageGenerationProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response(
            url="https://example.com/img.png",
            b64_json="base64data",
            revised_prompt="revised prompt",
        )

        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.images.generate = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.generate(
                ImageGenerationRequest(prompt="a cat")
            )

        assert isinstance(result, ImageGenerationResult)
        assert result.image_url == "https://example.com/img.png"
        assert result.image_b64 == "base64data"
        assert result.provider_name == "openaiimagegeneration"
        assert result.model_name == "dall-e-3"
        assert result.revised_prompt == "revised prompt"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_with_model_override(self):
        provider = OpenAIImageGenerationProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response()

        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.images.generate = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.generate(
                ImageGenerationRequest(prompt="text", model="dall-e-2")
            )

            call_kwargs = mock_client.images.generate.call_args.kwargs
            assert call_kwargs["model"] == "dall-e-2"

    @pytest.mark.asyncio
    async def test_generate_raises_after_max_retries(self):
        provider = OpenAIImageGenerationProvider(api_key="key", max_retries=2)

        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.images.generate = AsyncMock(side_effect=Exception("API error"))
            mock_cls.return_value = mock_client

            with pytest.raises(ImageGenerationError) as exc_info:
                await provider.generate(ImageGenerationRequest(prompt="text"))

            assert "2 attempts" in str(exc_info.value)
            assert exc_info.value.provider == "openaiimagegeneration"
            assert exc_info.value.retryable is True


class TestOpenAIImageGenerationProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        provider = OpenAIImageGenerationProvider(api_key="key")
        mock_response = _make_mock_response()

        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.images.generate = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        provider = OpenAIImageGenerationProvider(api_key="key")

        with patch("app.etl.image_generation.providers.openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.images.generate = AsyncMock(side_effect=Exception("unreachable"))
            mock_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is False
