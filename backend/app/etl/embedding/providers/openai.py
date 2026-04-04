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
        model = request.model or self.model
        dimensions = request.dimensions or self.dimensions
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.monotonic()
                client = self._get_client()

                response = await client.embeddings.create(
                    model=model,
                    input=request.text,
                    dimensions=dimensions,
                )

                latency_ms = (time.monotonic() - start_time) * 1000

                embedding_data = response.data[0]
                embedding = embedding_data.embedding

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "total": response.usage.total_tokens,
                    }

                return EmbeddingResult(
                    embedding=embedding,
                    provider_name=self.name,
                    model_name=model,
                    dimensions=len(embedding),
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                )

            except Exception as exc:
                last_error = exc
                if not self._is_retryable_error(exc):
                    raise EmbeddingError(
                        message=str(exc),
                        provider=self.name,
                        retryable=False,
                    )
                if attempt < self.max_retries - 1:
                    await __import__("asyncio").sleep(2 ** attempt)

        raise EmbeddingError(
            message=f"Embedding generation failed after {self.max_retries} retries: {last_error}",
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
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.monotonic()
                client = self._get_client()

                response = await client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )

                latency_ms = (time.monotonic() - start_time) * 1000

                token_usage = None
                if response.usage:
                    token_usage = {
                        "input": response.usage.prompt_tokens,
                        "total": response.usage.total_tokens,
                    }

                results = []
                for embedding_data in response.data:
                    embedding = embedding_data.embedding
                    results.append(
                        EmbeddingResult(
                            embedding=embedding,
                            provider_name=self.name,
                            model_name=self.model,
                            dimensions=len(embedding),
                            token_usage=token_usage,
                            latency_ms=latency_ms,
                        )
                    )

                return results

            except Exception as exc:
                last_error = exc
                if not self._is_retryable_error(exc):
                    raise EmbeddingError(
                        message=str(exc),
                        provider=self.name,
                        retryable=False,
                    )
                if attempt < self.max_retries - 1:
                    await __import__("asyncio").sleep(2 ** attempt)

        raise EmbeddingError(
            message=f"Batch embedding failed after {self.max_retries} retries: {last_error}",
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
            await client.embeddings.create(
                model=self.model,
                input="test",
            )
            return True
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
        retryable_keywords = ["timeout", "rate limit", "connection refused", "connection error", "network"]
        return any(keyword in error_str for keyword in retryable_keywords)
