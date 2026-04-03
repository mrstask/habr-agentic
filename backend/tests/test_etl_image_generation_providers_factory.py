"""Tests for the image generation provider factory and registry."""

from unittest.mock import patch

import pytest

from app.etl.image_generation.base import (
    BaseImageGenerationProvider,
    ImageGenerationError,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from app.etl.image_generation.providers.factory import (
    _IMAGE_PROVIDER_REGISTRY,
    create_image_provider,
    get_registered_image_providers,
    register_image_provider,
)


class DummyImageProvider(BaseImageGenerationProvider):
    """Minimal concrete provider for factory tests."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return ImageGenerationResult(
            image_url="https://example.com/image.png",
            provider_name=self.name,
            model_name=self.model,
        )

    async def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before and after each test."""
    _IMAGE_PROVIDER_REGISTRY.clear()
    yield
    _IMAGE_PROVIDER_REGISTRY.clear()


class TestRegisterImageProvider:
    def test_register_and_list(self):
        register_image_provider("dummy", DummyImageProvider)
        assert "dummy" in get_registered_image_providers()

    def test_register_overwrites(self):
        register_image_provider("dummy", DummyImageProvider)
        register_image_provider("dummy", DummyImageProvider)
        assert get_registered_image_providers() == ["dummy"]


class TestCreateImageProvider:
    def test_create_with_explicit_api_key(self):
        register_image_provider("openai", DummyImageProvider)
        provider = create_image_provider(api_key="my-key", model="my-model")
        assert isinstance(provider, DummyImageProvider)
        assert provider.api_key == "my-key"
        assert provider.model == "my-model"

    def test_create_unknown_provider_raises_value_error(self):
        register_image_provider("dummy", DummyImageProvider)
        with pytest.raises(ValueError) as exc_info:
            create_image_provider(provider_name="nonexistent", api_key="key")
        assert "Unknown image generation provider" in str(exc_info.value)

    def test_create_openai_with_explicit_api_key(self):
        """Test creating an openai provider with explicit api_key (no settings lookup)."""
        register_image_provider("openai", DummyImageProvider)
        provider = create_image_provider(api_key="openai-key", model="dall-e-2")
        assert isinstance(provider, DummyImageProvider)
        assert provider.api_key == "openai-key"
        assert provider.model == "dall-e-2"

    def test_create_openai_with_settings(self):
        """Test creating an openai provider using settings for api_key and model."""
        register_image_provider("openai", DummyImageProvider)
        with patch("app.etl.image_generation.providers.factory.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "openai-key"
            mock_settings.IMAGE_GENERATION_MODEL = "dall-e-3"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            provider = create_image_provider()
            assert isinstance(provider, DummyImageProvider)
            assert provider.api_key == "openai-key"
            assert provider.model == "dall-e-3"

    def test_create_missing_api_key_raises_image_generation_error(self):
        """Test that missing api_key raises ImageGenerationError."""
        register_image_provider("openai", DummyImageProvider)
        with patch("app.etl.image_generation.providers.factory.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.IMAGE_GENERATION_MODEL = "dall-e-3"

            with pytest.raises(ImageGenerationError) as exc_info:
                create_image_provider()
            assert exc_info.value.retryable is False

    def test_create_with_explicit_kwargs_override(self):
        register_image_provider("openai", DummyImageProvider)
        provider = create_image_provider(
            api_key="explicit-key",
            model="explicit-model",
            timeout=999,
        )
        assert provider.api_key == "explicit-key"
        assert provider.model == "explicit-model"
        assert provider._extra_config.get("timeout") == 999
