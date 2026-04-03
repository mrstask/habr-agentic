"""Tests for the translation provider factory and registry."""

from unittest.mock import patch

import pytest

from app.etl.translation.base import BaseTranslationProvider, TranslationError, TranslationResult, ProofreadingResult
from app.etl.translation.providers.factory import (
    _PROVIDER_REGISTRY,
    create_fallback_provider,
    create_provider,
    get_registered_providers,
    register_provider,
)


class DummyProvider(BaseTranslationProvider):
    """Minimal concrete provider for factory tests."""

    async def translate(self, request):
        return TranslationResult(
            translated_text="translated",
            provider_name=self.name,
            model_name=self.model,
        )

    async def proofread(self, text, context=None):
        return ProofreadingResult(
            corrected_text=text,
            corrections_made=0,
            provider_name=self.name,
            model_name=self.model,
        )

    async def health_check(self):
        return True


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before and after each test."""
    _PROVIDER_REGISTRY.clear()
    yield
    _PROVIDER_REGISTRY.clear()


class TestRegisterProvider:
    def test_register_and_list(self):
        register_provider("dummy", DummyProvider)
        assert "dummy" in get_registered_providers()

    def test_register_overwrites(self):
        register_provider("dummy", DummyProvider)
        register_provider("dummy", DummyProvider)
        assert get_registered_providers() == ["dummy"]


class TestCreateProvider:
    def test_create_with_explicit_api_key(self):
        register_provider("dummy", DummyProvider)
        provider = create_provider("dummy", api_key="my-key", model="my-model")
        assert isinstance(provider, DummyProvider)
        assert provider.api_key == "my-key"
        assert provider.model == "my-model"

    def test_create_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            create_provider("nonexistent", api_key="key")
        assert "Unknown translation provider" in str(exc_info.value)

    def test_create_grok_with_explicit_api_key(self):
        """Test creating a grok provider with explicit api_key (no settings lookup)."""
        register_provider("grok", DummyProvider)
        provider = create_provider("grok", api_key="grok-key", model="grok-3-mini")
        assert isinstance(provider, DummyProvider)
        assert provider.api_key == "grok-key"
        assert provider.model == "grok-3-mini"

    def test_create_openai_with_explicit_api_key(self):
        """Test creating an openai provider with explicit api_key (no settings lookup)."""
        register_provider("openai", DummyProvider)
        provider = create_provider("openai", api_key="openai-key", model="gpt-4o-mini")
        assert isinstance(provider, DummyProvider)
        assert provider.api_key == "openai-key"
        assert provider.model == "gpt-4o-mini"

    def test_create_grok_with_settings(self):
        """Test creating a grok provider using settings for api_key and model."""
        register_provider("grok", DummyProvider)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.GROK_API_KEY = "grok-key"
            mock_settings.GROK_TRANSLATION_MODEL = "grok-3-mini"
            mock_settings.GROK_BASE_URL = "https://api.x.ai/v1"
            mock_settings.GROK_TIMEOUT_SECONDS = 120
            mock_settings.GROK_MAX_RETRIES = 3

            provider = create_provider("grok")
            assert isinstance(provider, DummyProvider)
            assert provider.api_key == "grok-key"
            assert provider.model == "grok-3-mini"

    def test_create_openai_with_settings(self):
        """Test creating an openai provider using settings for api_key and model."""
        register_provider("openai", DummyProvider)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "openai-key"
            mock_settings.OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            provider = create_provider("openai")
            assert isinstance(provider, DummyProvider)
            assert provider.api_key == "openai-key"
            assert provider.model == "gpt-4o-mini"

    def test_create_missing_api_key_raises_translation_error(self):
        """Test that missing api_key raises TranslationError for grok provider."""
        register_provider("grok", DummyProvider)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.GROK_API_KEY = None
            mock_settings.GROK_TRANSLATION_MODEL = "grok-3-mini"

            with pytest.raises(TranslationError) as exc_info:
                create_provider("grok")
            assert exc_info.value.retryable is False

    def test_create_with_explicit_kwargs_override(self):
        register_provider("dummy", DummyProvider)
        provider = create_provider(
            "dummy",
            api_key="explicit-key",
            model="explicit-model",
            timeout=999,
        )
        assert provider.api_key == "explicit-key"
        assert provider.model == "explicit-model"
        assert provider._extra_config.get("timeout") == 999


class TestCreateFallbackProvider:
    def test_fallback_grok_to_openai(self):
        register_provider("grok", DummyProvider)
        register_provider("openai", DummyProvider)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "openai-key"
            mock_settings.OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            fallback = create_fallback_provider("grok")
            assert fallback is not None
            assert fallback.name == "dummy"  # DummyProvider name

    def test_fallback_openai_to_grok(self):
        register_provider("grok", DummyProvider)
        register_provider("openai", DummyProvider)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.GROK_API_KEY = "grok-key"
            mock_settings.GROK_TRANSLATION_MODEL = "grok-3-mini"
            mock_settings.GROK_BASE_URL = "https://api.x.ai/v1"
            mock_settings.GROK_TIMEOUT_SECONDS = 120
            mock_settings.GROK_MAX_RETRIES = 3

            fallback = create_fallback_provider("openai")
            assert fallback is not None
            assert fallback.name == "dummy"  # DummyProvider name

    def test_fallback_unknown_primary_returns_none(self):
        register_provider("dummy", DummyProvider)
        result = create_fallback_provider("dummy")
        assert result is None

    def test_fallback_unregistered_fallback_returns_none(self):
        register_provider("grok", DummyProvider)
        # openai not registered
        result = create_fallback_provider("grok")
        assert result is None

    def test_fallback_missing_api_key_returns_none(self):
        register_provider("grok", DummyProvider)
        register_provider("openai", DummyProvider)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT_SECONDS = 120
            mock_settings.OPENAI_MAX_RETRIES = 3

            result = create_fallback_provider("grok")
            assert result is None
