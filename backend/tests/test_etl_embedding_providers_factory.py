"""
Tests for the embedding provider factory.

Tests the happy path of creating embedding providers via the factory,
including registration, configuration, and instantiation.
"""

import pytest
from unittest.mock import patch

from app.etl.embedding.providers.factory import (
    create_embedding_provider,
    get_registered_embedding_providers,
    register_embedding_provider,
)
from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider
from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider
from app.etl.embedding.base import BaseEmbeddingProvider


@pytest.fixture
def mock_settings():
    """Mock the settings module for testing."""
    with patch("app.etl.embedding.providers.factory.settings") as mock:
        mock.OPENAI_API_KEY = "test-api-key"
        mock.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
        mock.OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
        mock.OPENAI_TIMEOUT_SECONDS = 120
        mock.OPENAI_MAX_RETRIES = 3
        mock.EMBEDDING_DIMENSIONS = 1536
        mock.OLLAMA_BASE_URL = "http://localhost:11434"
        mock.OLLAMA_TIMEOUT_SECONDS = 300
        yield mock


def test_get_registered_embedding_providers():
    """Test that registered providers are returned."""
    providers = get_registered_embedding_providers()
    assert "openai" in providers
    assert "ollama" in providers


def test_register_embedding_provider():
    """Test registering a new provider."""
    class TestProvider(BaseEmbeddingProvider):
        async def embed(self, request):
            pass
        async def embed_batch(self, texts):
            pass
        async def health_check(self):
            return True

    register_embedding_provider("test", TestProvider)
    providers = get_registered_embedding_providers()
    assert "test" in providers


def test_create_openai_provider_with_api_key(mock_settings):
    """Test creating OpenAI provider with explicit API key."""
    provider = create_embedding_provider(
        provider_name="openai",
        api_key="explicit-key",
        model="text-embedding-3-large",
    )
    
    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.api_key == "explicit-key"
    assert provider.model == "text-embedding-3-large"
    assert provider.name == "openaiembedding"


def test_create_openai_provider_from_settings(mock_settings):
    """Test creating OpenAI provider using settings."""
    provider = create_embedding_provider(provider_name="openai")
    
    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.api_key == "test-api-key"
    assert provider.model == "text-embedding-3-small"
    assert provider.timeout == 120
    assert provider.max_retries == 3
    assert provider.dimensions == 1536


def test_create_ollama_provider(mock_settings):
    """Test creating Ollama provider."""
    provider = create_embedding_provider(provider_name="ollama")
    
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.model == "nomic-embed-text"
    assert provider.base_url == "http://localhost:11434"
    assert provider.timeout == 300
    assert provider.max_retries == 3


def test_create_ollama_provider_with_custom_config(mock_settings):
    """Test creating Ollama provider with custom configuration."""
    provider = create_embedding_provider(
        provider_name="ollama",
        model="custom-model",
        base_url="http://custom:11434",
        timeout=600,
    )
    
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.model == "custom-model"
    assert provider.base_url == "http://custom:11434"
    assert provider.timeout == 600


def test_create_provider_with_kwargs_override(mock_settings):
    """Test that explicit kwargs override settings."""
    provider = create_embedding_provider(
        provider_name="openai",
        api_key="override-key",
        timeout=300,
        max_retries=5,
    )
    
    assert provider.api_key == "override-key"
    assert provider.timeout == 300
    assert provider.max_retries == 5


def test_create_provider_unknown_name(mock_settings):
    """Test that unknown provider name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_embedding_provider(provider_name="unknown_provider")
