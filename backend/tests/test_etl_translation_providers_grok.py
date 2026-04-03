"""Tests for the Grok translation provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.etl.translation.base import (
    ProofreadingResult,
    TranslationError,
    TranslationRequest,
    TranslationResult,
)
from app.etl.translation.providers.grok import GrokTranslationProvider


def _make_mock_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
    """Create a mock OpenAI chat completion response."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


class TestGrokTranslationProviderInit:
    def test_default_values(self):
        provider = GrokTranslationProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "grok-3-mini"
        assert provider.base_url == "https://api.x.ai/v1"
        assert provider.timeout == 120
        assert provider.max_retries == 3
        # name is derived from class name: GrokTranslationProvider -> groktranslation
        assert provider.name == "groktranslation"

    def test_custom_values(self):
        provider = GrokTranslationProvider(
            api_key="key",
            model="grok-4",
            base_url="https://custom.api/v1",
            timeout=60,
            max_retries=5,
        )
        assert provider.model == "grok-4"
        assert provider.base_url == "https://custom.api/v1"
        assert provider.timeout == 60
        assert provider.max_retries == 5


class TestGrokTranslationProviderTranslate:
    @pytest.mark.asyncio
    async def test_translate_success(self):
        provider = GrokTranslationProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response("перекладений текст", 10, 20)

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.translate(
                TranslationRequest(source_text="original text")
            )

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "перекладений текст"
        assert result.provider_name == "groktranslation"
        assert result.model_name == "grok-3-mini"
        assert result.token_usage == {"input": 10, "output": 20, "total": 30}
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_translate_with_custom_system_prompt(self):
        provider = GrokTranslationProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response("translated")

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await provider.translate(
                TranslationRequest(
                    source_text="text",
                    system_prompt="custom prompt",
                )
            )

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == "custom prompt"

    @pytest.mark.asyncio
    async def test_translate_raises_after_max_retries(self):
        provider = GrokTranslationProvider(api_key="key", max_retries=2)

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API error")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(TranslationError) as exc_info:
                await provider.translate(
                    TranslationRequest(source_text="text")
                )

            assert "2 attempts" in str(exc_info.value)
            assert exc_info.value.provider == "groktranslation"


class TestGrokTranslationProviderProofread:
    @pytest.mark.asyncio
    async def test_proofread_success(self):
        provider = GrokTranslationProvider(api_key="key", max_retries=1)
        mock_response = _make_mock_response("виправлений текст", 15, 25)

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.proofread("текст з помилками")

        assert isinstance(result, ProofreadingResult)
        assert result.corrected_text == "виправлений текст"
        assert result.provider_name == "groktranslation"
        assert result.token_usage == {"input": 15, "output": 25, "total": 40}

    @pytest.mark.asyncio
    async def test_proofread_raises_after_max_retries(self):
        provider = GrokTranslationProvider(api_key="key", max_retries=1)

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("fail")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(TranslationError):
                await provider.proofread("text")


class TestGrokTranslationProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        provider = GrokTranslationProvider(api_key="key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        provider = GrokTranslationProvider(api_key="key")

        with patch(
            "app.etl.translation.providers.grok.AsyncOpenAI"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("unreachable")
            )
            mock_client_cls.return_value = mock_client

            result = await provider.health_check()
            assert result is False


class TestGrokTranslationProviderEstimateCorrections:
    def test_identical_texts(self):
        assert GrokTranslationProvider._estimate_corrections("same", "same") == 0

    def test_different_texts(self):
        original = "line1 line2 line3"
        corrected = "line1 changed line3"
        # symmetric difference: {"line2", "changed"} = 2
        assert GrokTranslationProvider._estimate_corrections(original, corrected) == 2
