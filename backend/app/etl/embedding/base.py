"""
Embedding provider base class and shared types.

Defines the abstract interface that all embedding providers must implement,
along with shared dataclasses for embedding requests and responses.

Usage::

    from app.etl.embedding.base import BaseEmbeddingProvider, EmbeddingRequest
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmbeddingRequest:
    """
    Encapsulates all data needed for an embedding generation operation.

    Attributes:
        text: The text to generate an embedding for.
        model: Optional model override (uses provider default if None).
        dimensions: Optional output dimensionality override.
    """
    text: str
    model: Optional[str] = None
    dimensions: Optional[int] = None


@dataclass
class EmbeddingResult:
    """
    Result of an embedding generation operation.

    Attributes:
        embedding: The generated embedding vector.
        provider_name: Name of the provider that produced this result.
        model_name: Model name used for embedding generation.
        dimensions: Dimensionality of the embedding vector.
        token_usage: Optional token usage statistics (input, total).
        latency_ms: Time taken for the operation in milliseconds.
        error: Optional error message if the operation partially failed.
    """
    embedding: list[float]
    provider_name: str
    model_name: str
    dimensions: int
    token_usage: Optional[dict[str, int]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding providers (OpenAI, Ollama, etc.) must inherit from this class
    and implement the embed and health_check methods.

    Subclasses should handle their own API client initialization,
    retry logic, and error handling.

    Attributes:
        name: Human-readable provider name (e.g., 'openai', 'ollama').
        model: Model identifier used for embedding generation.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "", **kwargs) -> None:
        """
        Initialize the embedding provider.

        Args:
            api_key: API key for the provider service (may be None for local providers).
            model: Model identifier to use for embedding generation.
            **kwargs: Additional provider-specific configuration
                      (base_url, timeout, max_retries, dimensions, etc.).
        """
        self.name: str = self.__class__.__name__.lower().replace("provider", "")
        self.model: str = model
        self.api_key: Optional[str] = api_key
        self._extra_config: dict = kwargs

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """
        Generate an embedding vector for the given text.

        Args:
            request: EmbeddingRequest containing the text and options.

        Returns:
            EmbeddingResult with the embedding vector and metadata.

        Raises:
            EmbeddingError: If the embedding generation fails after retries.
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """
        Generate embedding vectors for multiple texts in a single batch.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of EmbeddingResult objects, one per input text.

        Raises:
            EmbeddingError: If the batch embedding fails after retries.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider API is reachable and ready.

        Returns:
            True if the provider is healthy and ready to accept requests.
        """
        ...


class EmbeddingError(Exception):
    """
    Exception raised when an embedding operation fails.

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
        Initialize an EmbeddingError.

        Args:
            message: Human-readable error description.
            provider: Name of the provider that failed.
            retryable: Whether this error is transient and can be retried.
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
