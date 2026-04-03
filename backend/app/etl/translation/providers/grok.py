"""
Grok (xAI) translation provider.

Implements the BaseTranslationProvider interface using the xAI Grok API
via its OpenAI-compatible endpoint. Grok is the primary translation provider
for the Habr Agentic Pipeline.

Usage::

    from app.etl.translation.providers.grok import GrokTranslationProvider
    from app.etl.translation.base import TranslationRequest

    provider = GrokTranslationProvider(api_key="...", model="grok-3-mini")
    result = await provider.translate(TranslationRequest(source_text="..."))
"""

import asyncio
import logging
import time
from typing import Optional

from openai import AsyncOpenAI

from app.etl.translation.base import (
    BaseTranslationProvider,
    TranslationRequest,
    TranslationResult,
    ProofreadingResult,
    TranslationError,
)
from app.etl.translation.prompts.loader import (
    load_translation_prompt,
    load_proofreading_prompt,
)

logger = logging.getLogger(__name__)


class GrokTranslationProvider(BaseTranslationProvider):
    """
    Translation provider using xAI Grok API.

    Connects to the Grok API via its OpenAI-compatible endpoint
    (https://api.x.ai/v1). Handles translation and proofreading
    requests with retry logic and error handling.

    Args:
        api_key: xAI Grok API key.
        model: Grok model identifier (default: 'grok-3-mini').
        base_url: API base URL (default: 'https://api.x.ai/v1').
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "grok-3-mini",
        base_url: str = "https://api.x.ai/v1",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the Grok translation provider.

        Args:
            api_key: xAI Grok API key.
            model: Grok model identifier.
            base_url: API base URL for the OpenAI-compatible endpoint.
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
        """
        super().__init__(api_key=api_key, model=model)
        self.base_url: str = base_url
        self.timeout: int = timeout
        self.max_retries: int = max_retries

    def _create_client(self) -> AsyncOpenAI:
        """Create an OpenAI-compatible async client configured for Grok."""
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate text using the Grok API.

        Sends the source text to the Grok model with a system prompt
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
                client = self._create_client()
                start_time = time.monotonic()

                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request.source_text},
                    ],
                    temperature=0.3,
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

                logger.info(
                    "Grok translation completed: %d tokens, %.0fms (attempt %d)",
                    token_usage.get("total", 0) if token_usage else 0,
                    latency_ms,
                    attempt,
                )

                return TranslationResult(
                    translated_text=translated_text,
                    provider_name=self.name,
                    model_name=self.model,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Grok translation attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)

        raise TranslationError(
            message=f"Translation failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=True,
        )

    async def proofread(self, text: str, context: Optional[str] = None) -> ProofreadingResult:
        """
        Proofread Ukrainian text using the Grok API.

        Sends the Ukrainian text to the Grok model with a system prompt
        instructing it to correct grammar, style, and fluency issues
        while preserving the original meaning.

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
                client = self._create_client()
                start_time = time.monotonic()

                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.2,
                )

                latency_ms = (time.monotonic() - start_time) * 1000

                corrected_text = response.choices[0].message.content or ""

                # Count corrections by comparing original and corrected text
                corrections_made = self._estimate_corrections(text, corrected_text)

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                logger.info(
                    "Grok proofreading completed: %d corrections, %d tokens, %.0fms (attempt %d)",
                    corrections_made,
                    token_usage.get("total", 0) if token_usage else 0,
                    latency_ms,
                    attempt,
                )

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
                logger.warning(
                    "Grok proofreading attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)

        raise TranslationError(
            message=f"Proofreading failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=True,
        )

    async def health_check(self) -> bool:
        """
        Check if the Grok API is reachable and the API key is valid.

        Sends a minimal test request to the Grok API and verifies
        the response.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            client = self._create_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=10,
            )
            return response is not None and len(response.choices) > 0
        except Exception as exc:
            logger.warning("Grok health check failed: %s", exc)
            return False

    def _build_system_prompt(
        self,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Build the system prompt for Grok translation.

        Constructs a prompt that instructs Grok to translate technical
        articles from Russian to Ukrainian, preserving formatting and
        technical terminology.

        Args:
            source_language: BCP-47 source language code.
            target_language: BCP-47 target language code.
            context: Optional article context (title, tags, hubs).

        Returns:
            Formatted system prompt string for Grok.
        """
        return load_translation_prompt(
            source_language=source_language,
            target_language=target_language,
            context=context,
        )

    def _build_proofreading_prompt(self, context: Optional[str] = None) -> str:
        """
        Build the system prompt for Grok proofreading.

        Constructs a prompt that instructs Grok to proofread Ukrainian
        text for grammar, style, and fluency while preserving meaning.

        Args:
            context: Optional article context.

        Returns:
            Formatted proofreading system prompt string.
        """
        return load_proofreading_prompt(context=context)

    @staticmethod
    def _estimate_corrections(original: str, corrected: str) -> int:
        """
        Estimate the number of corrections by comparing original and corrected text.

        Uses a simple word-level diff to count changes.

        Args:
            original: The original text before proofreading.
            corrected: The corrected text after proofreading.

        Returns:
            Estimated number of corrections made.
        """
        if original == corrected:
            return 0

        original_words = set(original.split())
        corrected_words = set(corrected.split())

        added = corrected_words - original_words
        removed = original_words - corrected_words

        return len(added) + len(removed)
