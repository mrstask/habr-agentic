"""
OpenAI embedding provider.

Implements the BaseEmbeddingProvider interface using the OpenAI Embeddings API.
Used for generating article embeddings for deduplication and similarity search.

Usage::

    from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider
    from app.etl.embedding.base import EmbeddingRequest

    provider = OpenAIEmbeddingProvider(api_key="...", model="text-embedding-3-small")
    result = await provider.embed(EmbeddingRequest(text="..."))
"""

import time
from typing import Optional

from openai import AsyncOpenAI
from openai.types import CreateEmbeddingResponse

from app.etl.embedding.base import (
    BaseEmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingError,
)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    Embedding provider using OpenAI Embeddings API.

    Connects to the OpenAI API for embedding generation.
    Supports models like text-embedding-3-small and text-embedding-3-large.

    Args:
        api_key: OpenAI API key.
        model: OpenAI embedding model identifier (default: 'text-embedding-3-small').
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
        dimensions: Optional output dimensionality override.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        timeout: int = 120,
        max_retries: int = 3,
        dimensions: Optional[int] = None,
    ) -> None:
        """
        Initialize the OpenAI embedding provider.

        Args:
            api_key: OpenAI API key.
            model: OpenAI embedding model identifier.
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
            dimensions: Optional output dimensionality override.
        """
        super().__init__(api_key=api_key, model=model)
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.dimensions: Optional[int] = dimensions
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

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """
        Generate an embedding vector for the given text using the OpenAI API.

        Sends the text to the OpenAI embeddings endpoint and returns
        the resulting vector.

        Args:
            request: EmbeddingRequest containing the text and options.

        Returns:
            EmbeddingResult with the embedding vector and metadata.

        Raises:
            EmbeddingError: If the embedding generation fails after all retries.
        """
        start_time = time.time()
        last_error = None

        model = request.model or self.model
        dimensions = request.dimensions or self.dimensions

        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                params: dict = {
                    "model": model,
                    "input": request.text,
                }
                if dimensions is not None:
                    params["dimensions"] = dimensions

                response: CreateEmbeddingResponse = await client.embeddings.create(**params)

                embedding = response.data[0].embedding
                actual_dimensions = len(embedding)

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "total": response.usage.total_tokens,
                    }

                latency_ms = (time.time() - start_time) * 1000

                return EmbeddingResult(
                    embedding=embedding,
                    provider_name=self.name,
                    model_name=model,
                    dimensions=actual_dimensions,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries - 1:
                    break
                if not self._is_retryable_error(e):
                    break

        raise EmbeddingError(
            message=f"Embedding failed after {self.max_retries} attempts: {str(last_error)}",
            provider=self.name,
            retryable=True,
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """
        Generate embedding vectors for multiple texts in a single batch.

        Sends all texts to the OpenAI embeddings endpoint in one request
        and returns a list of results.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of EmbeddingResult objects, one per input text.

        Raises:
            EmbeddingError: If the batch embedding fails after retries.
        """
        start_time = time.time()
        last_error = None

        model = self.model
        dimensions = self.dimensions

        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                params: dict = {
                    "model": model,
                    "input": texts,
                }
                if dimensions is not None:
                    params["dimensions"] = dimensions

                response: CreateEmbeddingResponse = await client.embeddings.create(**params)

                results = []
                for i, item in enumerate(response.data):
                    embedding = item.embedding
                    actual_dimensions = len(embedding)
                    results.append(
                        EmbeddingResult(
                            embedding=embedding,
                            provider_name=self.name,
                            model_name=model,
                            dimensions=actual_dimensions,
                            latency_ms=(time.time() - start_time) * 1000,
                        )
                    )

                # Attach token usage to the first result if available
                if response.usage and results:
                    results[0].token_usage = {
                        "input": response.usage.prompt_tokens,
                        "total": response.usage.total_tokens,
                    }

                return results

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries - 1:
                    break
                if not self._is_retryable_error(e):
                    break

        raise EmbeddingError(
            message=f"Batch embedding failed after {self.max_retries} attempts: {str(last_error)}",
            provider=self.name,
            retryable=True,
        )

    async def health_check(self) -> bool:
        """
        Check if the OpenAI API is reachable and the API key is valid.

        Sends a minimal test embedding request and verifies the response.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            client = self._get_client()
            response: CreateEmbeddingResponse = await client.embeddings.create(
                model=self.model,
                input="test",
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
