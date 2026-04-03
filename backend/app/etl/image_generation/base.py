"""
Image generation provider base class and shared types.

Defines the abstract interface that all image generation providers must implement,
along with shared dataclasses for image generation requests and responses.

Usage::

    from app.etl.image_generation.base import BaseImageGenerationProvider, ImageGenerationRequest
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ImageGenerationRequest:
    """
    Encapsulates all data needed for an image generation operation.

    Attributes:
        prompt: Text description of the image to generate.
        model: Optional model override (uses provider default if None).
        size: Image resolution (e.g., '1024x1024', '1792x1024').
        quality: Image quality setting (e.g., 'standard', 'hd').
        style: Image style (e.g., 'vivid', 'natural').
        n: Number of images to generate (default: 1).
    """
    prompt: str
    model: Optional[str] = None
    size: str = "1792x1024"
    quality: str = "standard"
    style: str = "vivid"
    n: int = 1


@dataclass
class ImageGenerationResult:
    """
    Result of an image generation operation.

    Attributes:
        image_url: URL of the generated image (if available).
        image_b64: Base64-encoded image data (if available).
        provider_name: Name of the provider that produced this result.
        model_name: Model name used for image generation.
        revised_prompt: The prompt as revised by the model (if available).
        token_usage: Optional token usage statistics.
        latency_ms: Time taken for the operation in milliseconds.
        error: Optional error message if the operation partially failed.
    """
    image_url: Optional[str] = None
    image_b64: Optional[str] = None
    provider_name: str = ""
    model_name: str = ""
    revised_prompt: Optional[str] = None
    token_usage: Optional[dict[str, int]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class BaseImageGenerationProvider(ABC):
    """
    Abstract base class for image generation providers.

    All image generation providers (OpenAI DALL-E, etc.) must inherit from this class
    and implement the generate and health_check methods.

    Subclasses should handle their own API client initialization,
    retry logic, and error handling.

    Attributes:
        name: Human-readable provider name (e.g., 'openai').
        model: Model identifier used for image generation.
    """

    def __init__(self, api_key: str, model: str = "", **kwargs) -> None:
        """
        Initialize the image generation provider.

        Args:
            api_key: API key for the provider service.
            model: Model identifier to use for image generation.
            **kwargs: Additional provider-specific configuration
                      (base_url, timeout, max_retries, etc.).
        """
        self.name: str = self.__class__.__name__.lower().replace("provider", "")
        self.model: str = model
        self.api_key: str = api_key
        self._extra_config: dict = kwargs

    @abstractmethod
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """
        Generate an image from a text prompt.

        Args:
            request: ImageGenerationRequest containing the prompt and options.

        Returns:
            ImageGenerationResult with the generated image data and metadata.

        Raises:
            ImageGenerationError: If the image generation fails after retries.
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


class ImageGenerationError(Exception):
    """
    Exception raised when an image generation operation fails.

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
        Initialize an ImageGenerationError.

        Args:
            message: Human-readable error description.
            provider: Name of the provider that failed.
            retryable: Whether this error is transient and can be retried.
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
