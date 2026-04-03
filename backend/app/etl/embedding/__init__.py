"""
Embedding ETL module.

Provides embedding provider abstractions, concrete implementations,
and factory functions for the Habr Agentic Pipeline.

Submodules:
    base: Abstract base class and shared data types.
    providers: Concrete provider implementations (OpenAI, Ollama).
"""

from app.etl.embedding.base import (
    BaseEmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingError,
)
from app.etl.embedding.providers.factory import (
    create_embedding_provider,
    register_embedding_provider,
    get_registered_embedding_providers,
)

__all__ = [
    "BaseEmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddingError",
    "create_embedding_provider",
    "register_embedding_provider",
    "get_registered_embedding_providers",
]
