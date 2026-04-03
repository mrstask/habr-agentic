"""
Translation provider base class and shared types.

Defines the abstract interface that all translation providers must implement,
along with shared dataclasses for translation requests and responses.

Usage::

    from app.etl.translation.base import BaseTranslationProvider, TranslationResult
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranslationRequest:
    """
    Encapsulates all data needed for a translation operation.

    Attributes:
        source_text: The original Russian text to translate.
        source_language: BCP-47 source language code (default 'ru').
        target_language: BCP-47 target language code (default 'uk').
        context: Optional context about the article (title, tags, hubs)
                 to improve translation quality.
        system_prompt: Optional custom system prompt override.
    """
    source_text: str
    source_language: str = "ru"
    target_language: str = "uk"
    context: Optional[str] = None
    system_prompt: Optional[str] = None


@dataclass
class TranslationResult:
    """
    Result of a translation operation.

    Attributes:
        translated_text: The translated Ukrainian text.
        provider_name: Name of the provider that produced this result.
        model_name: Model name used for the translation.
        token_usage: Optional token usage statistics (input, output, total).
        latency_ms: Time taken for the translation in milliseconds.
        error: Optional error message if the translation partially failed.
    """
    translated_text: str
    provider_name: str
    model_name: str
    token_usage: Optional[dict[str, int]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ProofreadingResult:
    """
    Result of a proofreading operation.

    Attributes:
        corrected_text: The proofread and corrected Ukrainian text.
        corrections_made: Number of corrections applied.
        provider_name: Name of the provider that produced this result.
        model_name: Model name used for proofreading.
        token_usage: Optional token usage statistics.
        latency_ms: Time taken for proofreading in milliseconds.
        error: Optional error message.
    """
    corrected_text: str
    corrections_made: int
    provider_name: str
    model_name: str
    token_usage: Optional[dict[str, int]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class BaseTranslationProvider(ABC):
    """
    Abstract base class for translation providers.

    All translation providers (Grok, OpenAI, etc.) must inherit from this class
    and implement the translate and proofread methods.

    Subclasses should handle their own API client initialization,
    retry logic, and error handling.

    Attributes:
        name: Human-readable provider name (e.g., 'grok', 'openai').
        model: Model identifier used for translation.
    """

    def __init__(self, api_key: str, model: str, **kwargs) -> None:
        """
        Initialize the translation provider.

        Args:
            api_key: API key for the provider service.
            model: Model identifier to use for translation.
            **kwargs: Additional provider-specific configuration
                      (base_url, timeout, max_retries, etc.).
        """
        self.name: str = self.__class__.__name__.lower().replace("provider", "")
        self.model: str = model
        self.api_key: str = api_key
        self._extra_config: dict = kwargs

    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate text from source language to target language.

        Args:
            request: TranslationRequest containing the source text and options.

        Returns:
            TranslationResult with the translated text and metadata.

        Raises:
            TranslationError: If the translation fails after retries.
        """
        ...

    @abstractmethod
    async def proofread(self, text: str, context: Optional[str] = None) -> ProofreadingResult:
        """
        Proofread and correct Ukrainian text for grammar, style, and fluency.

        Args:
            text: The Ukrainian text to proofread.
            context: Optional context about the article for better corrections.

        Returns:
            ProofreadingResult with the corrected text and metadata.

        Raises:
            TranslationError: If proofreading fails after retries.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider API is reachable and the API key is valid.

        Returns:
            True if the provider is healthy and ready to accept requests.
        """
        ...

    def _build_system_prompt(
        self,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Build the system prompt for translation.

        Subclasses may override this to customize the prompt format
        for their specific model.

        Args:
            source_language: BCP-47 source language code.
            target_language: BCP-47 target language code.
            context: Optional article context.

        Returns:
            Formatted system prompt string.
        """
        context_info = f"- Article context: {context}" if context else ""
        return (
            f"You are a professional translator specializing in technical articles.\n\n"
            f"Translate the following text from {source_language} to {target_language}.\n\n"
            f"{context_info}"
        )

    def _build_proofreading_prompt(self, context: Optional[str] = None) -> str:
        """
        Build the system prompt for proofreading.

        Subclasses may override this to customize the prompt format.

        Args:
            context: Optional article context.

        Returns:
            Formatted proofreading system prompt string.
        """
        context_info = f"- Article context: {context}" if context else ""
        return (
            f"You are a professional editor specializing in technical articles.\n\n"
            f"Proofread and correct the text.\n\n"
            f"{context_info}"
        )


class TranslationError(Exception):
    """
    Exception raised when a translation operation fails.

    Attributes:
        message: Human-readable error description.
        provider: Name of the provider that failed.
        retryable: Whether this error is transient and can be retried.
    """

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        retryable: bool = True,
    ) -> None:
        """
        Initialize a TranslationError.

        Args:
            message: Human-readable error description.
            provider: Name of the provider that failed.
            retryable: Whether this error is transient and can be retried.
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
