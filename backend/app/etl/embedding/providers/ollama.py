"""
Ollama embedding provider.

Implements the BaseEmbeddingProvider interface using the local Ollama API.
Used for generating article embeddings for deduplication and similarity search
without relying on cloud providers.

Usage::

    from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider
    from app.etl.embedding.base import EmbeddingRequest

    provider = OllamaEmbeddingProvider(model="nomic-embed-text")
    result = await provider.embed(EmbeddingRequest(text="..."))
"""

import time
from typing import Optional

import httpx

from app.etl.embedding.base import (
    BaseEmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingError,
)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """
    Embedding provider using local Ollama API.

    Connects to a locally running Ollama server for embedding generation.
    Supports models like nomic-embed-text.

    Args:
        model: Ollama embedding model identifier (default: 'nomic-embed-text').
        base_url: Ollama server base URL (default: 'http://localhost:11434').
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the Ollama embedding provider.

        Args:
            model: Ollama embedding model identifier.
            base_url: Ollama server base URL.
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
        """
        super().__init__(api_key=None, model=model)
        self.base_url: str = base_url
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """
        Generate an embedding vector for the given text using the Ollama API.

        Sends the text to the local Ollama embeddings endpoint and returns
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

        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                response = await client.post(
                    "/api/embeddings",
                    json={
                        "model": model,
                        "prompt": request.text,
                    },
                )
                response.raise_for_status()
                response_data = response.json()

                embedding = response_data["embedding"]
                latency_ms = (time.time() - start_time) * 1000

                return EmbeddingResult(
                    embedding=embedding,
                    provider_name=self.name,
                    model_name=model,
                    dimensions=len(embedding),
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries - 1:
                    break
                if not self._is_retryable_error(e):
                    break

        latency_ms = (time.time() - start_time) * 1000
        raise EmbeddingError(
            message=f"Embedding failed after {self.max_retries} attempts: {str(last_error)}",
            provider=self.name,
            retryable=True,
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """
        Generate embedding vectors for multiple texts in a single batch.

        Sends texts to the Ollama embeddings endpoint and returns
        a list of results.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of EmbeddingResult objects, one per input text.

        Raises:
            EmbeddingError: If the batch embedding fails after retries.
        """
        # Ollama doesn't have a native batch API, so we call embed() for each text
        results = []
        for text in texts:
            try:
                result = await self.embed(EmbeddingRequest(text=text, model=self.model))
                results.append(result)
            except EmbeddingError as e:
                # Create a partial failure result
                results.append(
                    EmbeddingResult(
                        embedding=[],
                        provider_name=self.name,
                        model_name=self.model,
                        dimensions=0,
                        error=str(e),
                    )
                )
        return results

    async def health_check(self) -> bool:
        """
        Check if the Ollama server is reachable.

        Sends a request to the Ollama API health endpoint.

        Returns:
            True if the server responds successfully, False otherwise.
        """
        try:
            client = self._get_client()
            response = await client.get("/api/version")
            response.raise_for_status()
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
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "unavailable",
            "server error",
        ]
        return any(pattern in error_str for pattern in retryable_patterns)
