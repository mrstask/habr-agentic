"""
Embedding provider implementations.

Contains concrete embedding provider classes and the factory
for instantiating them based on configuration.

Submodules:
    openai: OpenAI embedding provider.
    ollama: Ollama embedding provider.
    factory: Provider factory and registry.
"""

from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider
from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider
from app.etl.embedding.providers.factory import (
    create_embedding_provider,
    register_embedding_provider,
    get_registered_embedding_providers,
)

__all__ = [
    "OpenAIEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "create_embedding_provider",
    "register_embedding_provider",
    "get_registered_embedding_providers",
]
