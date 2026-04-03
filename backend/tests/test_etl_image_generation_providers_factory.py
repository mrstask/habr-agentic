"""
Tests for the image generation provider factory.

Tests the happy path of creating image generation providers via the factory,
including registration, configuration, and instantiation.
"""

import pytest
from unittest.mock import patch

from app.etl.image_generation.providers.factory import (
    create_image_provider,
    get_registered_image_providers,
    register_image_provider,
)
from app.etl.image_generation.providers.openai import OpenAIImageGenerationProvider
from app.etl.image_generation.base import BaseImageGenerationProvider


@pytest.fixture
def mock_settings():
    """Mock the settings module for testing."""
    with patch("app.etl.image_generation.providers.factory.settings") as mock:
        mock.OPENAI_API_KEY = "test-api-key"
        mock.IMAGE_GENERATION_MODEL = "dall-e-3"
        mock.OPENAI_TIMEOUT_SECONDS = 120
        mock.OPENAI_MAX_RETRIES = 3
        yield mock


def test_get_registered_image_providers():
    """Test that registered providers are returned."""
    providers = get_registered_image_providers()
    assert "openai" in providers


def test_register_image_provider():
    """Test registering a new provider."""
    class TestProvider(BaseImageGenerationProvider):
        async def generate(self, request):
            pass
        async def health_check(self):
            return True

    register_image_provider("test", TestProvider)
    providers = get_registered_image_providers()
    assert "test" in providers


def test_create_provider_with_api_key(mock_settings):
    """Test creating provider with explicit API key."""
    provider = create_image_provider(
        api_key="explicit-key",
        model="dall-e-2",
    )

    assert isinstance(provider, OpenAIImageGenerationProvider)
    assert provider.api_key == "explicit-key"
    assert provider.model == "dall-e-2"
    assert provider.name == "openaiimagegeneration"


def test_create_provider_from_settings(mock_settings):
    """Test creating provider using settings."""
    provider = create_image_provider()

    assert isinstance(provider, OpenAIImageGenerationProvider)
    assert provider.api_key == "test-api-key"
    assert provider.model == "dall-e-3"
    assert provider.timeout == 120
    assert provider.max_retries == 3


def test_create_provider_with_kwargs_override(mock_settings):
    """Test that explicit kwargs override settings."""
    provider = create_image_provider(
        api_key="override-key",
        timeout=300,
        max_retries=5,
    )

    assert provider.api_key == "override-key"
    assert provider.timeout == 300
    assert provider.max_retries == 5


def test_create_provider_unknown_name(mock_settings):
    """Test that unknown provider name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown image generation provider"):
        create_image_provider(api_key="test-key", provider_name="unknown_provider")
