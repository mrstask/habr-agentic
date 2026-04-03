"""
OpenAI image generation provider.

Implements the BaseImageGenerationProvider interface using the OpenAI
DALL-E image generation API. Used by the pipeline's image_gen node
to generate article cover images.

Usage::

    from app.etl.image_generation.providers.openai import OpenAIImageGenerationProvider
    from app.etl.image_generation.base import ImageGenerationRequest

    provider = OpenAIImageGenerationProvider(api_key="...", model="dall-e-3")
    result = await provider.generate(ImageGenerationRequest(prompt="..."))
"""

import time
from typing import Optional

from openai import AsyncOpenAI
from openai.types.images_response import ImagesResponse

from app.etl.image_generation.base import (
    BaseImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageGenerationError,
)


class OpenAIImageGenerationProvider(BaseImageGenerationProvider):
    """
    Image generation provider using OpenAI DALL-E API.

    Connects to the OpenAI API for image generation.
    Supports DALL-E 3 with various sizes and quality settings.

    Args:
        api_key: OpenAI API key.
        model: OpenAI image model identifier (default: 'dall-e-3').
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "dall-e-3",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the OpenAI image generation provider.

        Args:
            api_key: OpenAI API key.
            model: OpenAI image model identifier.
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
        """
        super().__init__(api_key=api_key, model=model)
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the async OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """
        Generate an image from a text prompt using the OpenAI DALL-E API.

        Sends the prompt to the DALL-E model and returns the generated image.

        Args:
            request: ImageGenerationRequest containing the prompt and options.

        Returns:
            ImageGenerationResult with the generated image data and metadata.

        Raises:
            ImageGenerationError: If the image generation fails after all retries.
        """
        start_time = time.time()
        last_error = None

        model = request.model or self.model

        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                response: ImagesResponse = await client.images.generate(
                    model=model,
                    prompt=request.prompt,
                    size=request.size,
                    quality=request.quality,
                    style=request.style,
                    n=request.n,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Extract image data from response
                image_data = response.data[0]
                image_url = image_data.url if hasattr(image_data, 'url') else None
                image_b64 = image_data.b64_json if hasattr(image_data, 'b64_json') else None

                # Capture revised_prompt if available
                revised_prompt = None
                if hasattr(image_data, 'revised_prompt') and image_data.revised_prompt:
                    revised_prompt = image_data.revised_prompt

                return ImageGenerationResult(
                    image_url=image_url,
                    image_b64=image_b64,
                    provider_name=self.name,
                    model_name=model,
                    revised_prompt=revised_prompt,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries - 1:
                    break
                if not self._is_retryable_error(e):
                    break

        latency_ms = (time.time() - start_time) * 1000
        raise ImageGenerationError(
            message=f"Image generation failed after {self.max_retries} attempts: {str(last_error)}",
            provider=self.name,
            retryable=True,
        )

    async def health_check(self) -> bool:
        """
        Check if the OpenAI API is reachable and the API key is valid.

        Sends a minimal test image generation request and verifies the response.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            client = self._get_client()
            response: ImagesResponse = await client.images.generate(
                model=self.model,
                prompt="a simple test",
                size="1024x1024",
                n=1,
            )
            return len(response.data) > 0
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
