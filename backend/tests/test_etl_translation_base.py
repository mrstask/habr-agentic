"""Tests for translation base classes and dataclasses."""

import pytest

from app.etl.translation.base import (
    BaseTranslationProvider,
    ProofreadingResult,
    TranslationError,
    TranslationRequest,
    TranslationResult,
)


class ConcreteProvider(BaseTranslationProvider):
    """Concrete implementation for testing the abstract base class."""

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


class TestTranslationRequest:
    def test_defaults(self):
        req = TranslationRequest(source_text="hello")
        assert req.source_text == "hello"
        assert req.source_language == "ru"
        assert req.target_language == "uk"
        assert req.context is None
        assert req.system_prompt is None

    def test_custom_values(self):
        req = TranslationRequest(
            source_text="text",
            source_language="en",
            target_language="de",
            context="some context",
            system_prompt="custom prompt",
        )
        assert req.source_language == "en"
        assert req.target_language == "de"
        assert req.context == "some context"
        assert req.system_prompt == "custom prompt"


class TestTranslationResult:
    def test_basic_result(self):
        result = TranslationResult(
            translated_text="переклад",
            provider_name="openai",
            model_name="gpt-4o-mini",
        )
        assert result.translated_text == "переклад"
        assert result.provider_name == "openai"
        assert result.model_name == "gpt-4o-mini"
        assert result.token_usage is None
        assert result.latency_ms is None

    def test_full_result(self):
        result = TranslationResult(
            translated_text="переклад",
            provider_name="grok",
            model_name="grok-3-mini",
            token_usage={"input": 10, "output": 20, "total": 30},
            latency_ms=150.5,
        )
        assert result.token_usage["total"] == 30
        assert result.latency_ms == 150.5


class TestProofreadingResult:
    def test_basic_result(self):
        result = ProofreadingResult(
            corrected_text="corrected text",
            corrections_made=3,
            provider_name="openai",
            model_name="gpt-4o-mini",
        )
        assert result.corrected_text == "corrected text"
        assert result.corrections_made == 3
        assert result.provider_name == "openai"


class TestTranslationError:
    def test_basic_error(self):
        err = TranslationError(message="failed", provider="openai")
        assert err.message == "failed"
        assert err.provider == "openai"
        assert err.retryable is True
        assert str(err) == "failed"

    def test_non_retryable(self):
        err = TranslationError(message="bad key", provider="grok", retryable=False)
        assert err.retryable is False


class TestBaseTranslationProvider:
    def test_name_derived_from_class(self):
        provider = ConcreteProvider(api_key="test-key", model="test-model")
        assert provider.name == "concrete"

    def test_model_and_api_key_stored(self):
        provider = ConcreteProvider(api_key="secret", model="my-model")
        assert provider.model == "my-model"
        assert provider.api_key == "secret"

    def test_extra_config_stored(self):
        provider = ConcreteProvider(
            api_key="key", model="model", timeout=60, max_retries=5
        )
        assert provider._extra_config == {"timeout": 60, "max_retries": 5}

    @pytest.mark.asyncio
    async def test_translate_returns_result(self):
        provider = ConcreteProvider(api_key="key", model="model")
        result = await provider.translate(TranslationRequest(source_text="test"))
        assert result.translated_text == "translated"
        assert result.provider_name == "concrete"

    @pytest.mark.asyncio
    async def test_proofread_returns_result(self):
        provider = ConcreteProvider(api_key="key", model="model")
        result = await provider.proofread("some text")
        assert result.corrected_text == "some text"
        assert result.corrections_made == 0

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        provider = ConcreteProvider(api_key="key", model="model")
        assert await provider.health_check() is True
