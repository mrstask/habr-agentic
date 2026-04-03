"""
OpenAI translation provider.

Implements the BaseTranslationProvider interface using the OpenAI API.
OpenAI serves as the fallback translation provider when Grok is unavailable
or when explicitly configured as the primary provider.

Usage::

    from app.etl.translation.providers.openai import OpenAITranslationProvider
    from app.etl.translation.base import TranslationRequest

    provider = OpenAITranslationProvider(api_key="...", model="gpt-4o-mini")
    result = await provider.translate(TranslationRequest(source_text="..."))
"""

import time
from typing import Optional

from openai import AsyncOpenAI

from app.etl.translation.base import (
    BaseTranslationProvider,
    TranslationError,
    TranslationRequest,
    TranslationResult,
    ProofreadingResult,
)
from app.etl.translation.prompts.loader import (
    load_translation_prompt,
    load_proofreading_prompt,
)


class OpenAITranslationProvider(BaseTranslationProvider):
    """
    Translation provider using OpenAI API.

    Connects to the OpenAI API for translation and proofreading.
    Used as the fallback provider when Grok is unavailable.

    Args:
        api_key: OpenAI API key.
        model: OpenAI model identifier (default: 'gpt-4o-mini').
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the OpenAI translation provider.

        Args:
            api_key: OpenAI API key.
            model: OpenAI model identifier.
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
        """
        super().__init__(api_key=api_key, model=model)
        self.timeout: int = timeout
        self.max_retries: int = max_retries

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate text using the OpenAI API.

        Sends the source text to the OpenAI model with a system prompt
        instructing it to translate from Russian to Ukrainian.

        Args:
            request: TranslationRequest containing the source text and options.

        Returns:
            TranslationResult with the translated Ukrainian text.

        Raises:
            TranslationError: If the translation fails after all retries.
        """
        system_prompt = request.system_prompt or self._build_system_prompt(
            source_language=request.source_language,
            target_language=request.target_language,
            context=request.context,
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                client = AsyncOpenAI(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )

                start_time = time.monotonic()

                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request.source_text},
                    ],
                )

                latency_ms = (time.monotonic() - start_time) * 1000

                translated_text = response.choices[0].message.content or ""

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                return TranslationResult(
                    translated_text=translated_text,
                    provider_name=self.name,
                    model_name=self.model,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as exc:
                last_error = exc
                continue

        raise TranslationError(
            message=f"Translation failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=True,
        )

    async def proofread(self, text: str, context: Optional[str] = None) -> ProofreadingResult:
        """
        Proofread Ukrainian text using the OpenAI API.

        Sends the Ukrainian text to the OpenAI model with a system prompt
        instructing it to correct grammar, style, and fluency issues.

        Args:
            text: The Ukrainian text to proofread.
            context: Optional article context for better corrections.

        Returns:
            ProofreadingResult with the corrected text and metadata.

        Raises:
            TranslationError: If proofreading fails after all retries.
        """
        system_prompt = self._build_proofreading_prompt(context=context)

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                client = AsyncOpenAI(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )

                start_time = time.monotonic()

                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                )

                latency_ms = (time.monotonic() - start_time) * 1000

                corrected_text = response.choices[0].message.content or ""

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                corrections_made = self._estimate_corrections(text, corrected_text)

                return ProofreadingResult(
                    corrected_text=corrected_text,
                    corrections_made=corrections_made,
                    provider_name=self.name,
                    model_name=self.model,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as exc:
                last_error = exc
                continue

        raise TranslationError(
            message=f"Proofreading failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=True,
        )

    async def health_check(self) -> bool:
        """
        Check if the OpenAI API is reachable and the API key is valid.

        Sends a minimal test request to the OpenAI API and verifies
        the response.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=10,
            )

            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )

            return len(response.choices) > 0

        except Exception:
            return False

    def _build_system_prompt(
        self,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Build the system prompt for OpenAI translation.

        Constructs a prompt that instructs the OpenAI model to translate
        technical articles from Russian to Ukrainian.

        Args:
            source_language: BCP-47 source language code.
            target_language: BCP-47 target language code.
            context: Optional article context (title, tags, hubs).

        Returns:
            Formatted system prompt string for OpenAI.
        """
        return load_translation_prompt(
            source_language=source_language,
            target_language=target_language,
            context=context,
        )

    def _build_proofreading_prompt(self, context: Optional[str] = None) -> str:
        """
        Build the system prompt for OpenAI proofreading.

        Constructs a prompt that instructs the OpenAI model to proofread
        Ukrainian text for grammar, style, and fluency.

        Args:
            context: Optional article context.

        Returns:
            Formatted proofreading system prompt string.
        """
        return load_proofreading_prompt(context=context)

    @staticmethod
    def _estimate_corrections(original: str, corrected: str) -> int:
        """
        Estimate the number of corrections made between original and corrected text.

        Uses a simple word-level symmetric difference to count changed words.

        Args:
            original: The original text.
            corrected: The corrected text.

        Returns:
            Estimated number of corrections (changed words).
        """
        original_words = set(original.split())
        corrected_words = set(corrected.split())
        return len(original_words.symmetric_difference(corrected_words))
