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

import time
from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.etl.translation.base import (
    BaseTranslationProvider,
    TranslationRequest,
    TranslationResult,
    ProofreadingResult,
    TranslationError,
)


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
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the async OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    @staticmethod
    def _estimate_corrections(original: str, corrected: str) -> int:
        """
        Estimate the number of corrections between original and corrected text.

        Uses symmetric difference of word sets to estimate changes.

        Args:
            original: The original text.
            corrected: The corrected text.

        Returns:
            Estimated number of corrections (size of symmetric difference).
        """
        original_words = set(original.split())
        corrected_words = set(corrected.split())
        return len(original_words.symmetric_difference(corrected_words))

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
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Build system prompt
                system_prompt = request.system_prompt or self._build_system_prompt(
                    source_language=request.source_language,
                    target_language=request.target_language,
                    context=request.context,
                )

                # Create OpenAI-compatible async client with Grok base_url and api_key
                client = self._get_client()

                # Call chat.completions.create() with system + user messages
                response: ChatCompletion = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request.source_text},
                    ],
                )

                # Extract translated text from response
                translated_text = response.choices[0].message.content or ""

                # Capture token usage and latency
                latency_ms = (time.time() - start_time) * 1000
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

            except Exception as e:
                last_error = e
                # Don't retry on the last attempt
                if attempt >= self.max_retries - 1:
                    break
                # Check if error is retryable (network errors, rate limits, etc.)
                if not self._is_retryable_error(e):
                    break

        # All retries exhausted
        latency_ms = (time.time() - start_time) * 1000
        raise TranslationError(
            message=f"Translation failed after {self.max_retries} attempts: {str(last_error)}",
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
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Build proofreading prompt
                system_prompt = self._build_proofreading_prompt(context=context)

                # Create OpenAI-compatible async client
                client = self._get_client()

                # Call chat.completions.create() with proofreading instructions
                response: ChatCompletion = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                )

                # Extract corrected text from response
                corrected_text = response.choices[0].message.content or ""

                # Count corrections using symmetric difference of words
                corrections_made = self._estimate_corrections(text, corrected_text)

                # Capture token usage and latency
                latency_ms = (time.time() - start_time) * 1000
                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                return ProofreadingResult(
                    corrected_text=corrected_text,
                    corrections_made=corrections_made,
                    provider_name=self.name,
                    model_name=self.model,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries - 1:
                    break
                if not self._is_retryable_error(e):
                    break

        latency_ms = (time.time() - start_time) * 1000
        raise TranslationError(
            message=f"Proofreading failed after {self.max_retries} attempts: {str(last_error)}",
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
            client = self._get_client()
            response: ChatCompletion = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'ok'"},
                ],
                max_tokens=10,
            )
            return response.choices[0].message.content is not None
        except Exception:
            return False

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception that occurred.

        Returns:
            True if the error is transient and retryable.
        """
        error_str = str(error).lower()
        # Network errors, timeouts, rate limits are retryable
        retryable_patterns = [
            "timeout",
            "connection",
            "rate limit",
            "too many requests",
            "service unavailable",
            "internal server error",
            "gateway",
        ]
        return any(pattern in error_str for pattern in retryable_patterns)
