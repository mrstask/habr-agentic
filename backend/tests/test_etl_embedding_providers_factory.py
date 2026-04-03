"""Tests for the embedding provider factory and registry."""

from unittest.mock import patch

import pytest

from app.etl.embedding.base import BaseEmbeddingProvider, EmbeddingError, EmbeddingRequest, EmbeddingResult
from app.etl.embedding.providers.factory import (
    _EMBEDDING_PROVIDER_REGISTRY,
    create_embedding_provider,
    get_registered_embedding_providers,
    register_embedding_provider,
)


class DummyEmbeddingProvider(BaseEmbeddingProvider):
    """Minimal concrete provider for factory tests."""

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            embedding=[0.1],
            provider_name=self.name,
            model_name=self.model,
            dimensions=1,
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return []

    async def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before and after each test."""
    _EMBEDDING_PROVIDER_REGISTRY.clear()
    yield
    _EMBEDDING_PROVIDER_REGISTRY.clear()


class TestRegisterEmbeddingProvider:
    def test_register_and_list(self):
        register_embedding_provider("dummy", DummyEmbeddingProvider)
        assert "dummy" in get_registered_embedding_providers()

    def test_register_overwrites(self):
        register_embedding_provider("dummy", DummyEmbeddingProvider)
        register_embedding_provider("dummy", DummyEmbeddingProvider)
        assert get_registered_embedding_providers() == ["dummy"]


class TestCreateEmbeddingProvider:
    def test_create_with_explicit_api_key(self):
        register_embedding_provider("dummy", DummyEmbeddingProvider)
        provider = create_embedding_provider("dummy", api_key="my-key", model="my-model")
        assert isinstance(provider, DummyEmbeddingProvider)
        assert provider.api_key == "my-key"
        assert provider.model == "my-model"

    def test_create_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider("nonexistent", api_key="key")
        assert "Unknown embedding provider" in str(exc_info.value)

    def test_create_openai_with_explicit_api_key(self):
        """Test creating an openai provider with explicit api_key (no settings lookup)."""
        register_embedding_provider("openai", DummyEmbeddingProvider)
        provider = create_embedding_provider("openai", api_key="openai-key", model="gpt-4o-mini")
        assert isinstance(provider, DummyEmbeddingProvider)
        assert provider.api_key == "openai-key"
        assert provider.model == "gpt-4o-mini"

    def test_create_ollama_with_explicit_model(self):
        """Test creating an ollama provider with explicit model."""
        register_embedding_provider("ollama", DummyEmbeddingProvider)
        provider = create_embedding_provider("ollama", model="nomic-embed-text")
        assert isinstance(provider, DummyEmbeddingProvider)
        assert provider.model == "nomic-embed-text"

    def test_create_openai_with_settings(self):
        """Test creating an openai provider using settings for api_key and model."""
        register_embedding_provider("openai", DummyEmbeddingProvider)
        with patch("app.etl.embedding.providers.factory.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "openai-key"
            mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            provider = create_embedding_provider("openai")
            assert isinstance(provider, DummyEmbeddingProvider)
            assert provider.api_key == "openai-key"
            assert provider.model == "text-embedding-3-small"

    def test_create_ollama_with_settings(self):
        """Test creating an ollama provider using settings for model."""
        register_embedding_provider("ollama", DummyEmbeddingProvider)
        with patch("app.etl.embedding.providers.factory.settings") as mock_settings:
            mock_settings.OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
            mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_settings.OLLAMA_TIMEOUT_SECONDS = 300

            provider = create_embedding_provider("ollama")
            assert isinstance(provider, DummyEmbeddingProvider)
            assert provider.model == "nomic-embed-text"

    def test_create_openai_missing_api_key_raises_embedding_error(self):
        """Test that missing api_key raises EmbeddingError for openai provider."""
        register_embedding_provider("openai", DummyEmbeddingProvider)
        with patch("app.etl.embedding.providers.factory.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

            with pytest.raises(EmbeddingError) as exc_info:
                create_embedding_provider("openai")
            assert exc_info.value.retryable is False

    def test_create_with_explicit_kwargs_override(self):
        register_embedding_provider("dummy", DummyEmbeddingProvider)
        provider = create_embedding_provider(
            "dummy",
            api_key="explicit-key",
            model="explicit-model",
            timeout=999,
        )
        assert provider.api_key == "explicit-key"
        assert provider.model == "explicit-model"
        assert provider._extra_config.get("timeout") == 999

    def test_create_openai_with_dimensions_kwarg(self):
        """Test that dimensions kwarg is passed through for openai provider."""
        register_embedding_provider("openai", DummyEmbeddingProvider)
        with patch("app.etl.embedding.providers.factory.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "key"
            mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            provider = create_embedding_provider("openai", dimensions=1024)
            assert isinstance(provider, DummyEmbeddingProvider)
            assert provider._extra_config.get("dimensions") == 1024
