"""
Embedding provider factory and registry.

Provides a factory function to instantiate embedding providers based on
configuration, and a registry for managing available providers.

Usage::

    from app.etl.embedding.providers.factory import create_embedding_provider
    from app.core.config import settings

    provider = create_embedding_provider(settings.EMBEDDING_PROVIDER)
"""

import logging
from typing import Optional

from app.core.config import settings
from app.etl.embedding.base import BaseEmbeddingProvider, EmbeddingError

logger = logging.getLogger(__name__)

# Registry of available embedding provider classes
_EMBEDDING_PROVIDER_REGISTRY: dict[str, type[BaseEmbeddingProvider]] = {}


def register_embedding_provider(
    name: str,
    provider_class: type[BaseEmbeddingProvider],
) -> None:
    """
    Register an embedding provider class in the global registry.

    Args:
        name: Provider identifier (e.g., 'openai', 'ollama').
        provider_class: The provider class to register.
    """
    _EMBEDDING_PROVIDER_REGISTRY[name] = provider_class
    logger.info("Registered embedding provider: %s", name)


def get_registered_embedding_providers() -> list[str]:
    """
    Get a list of all registered embedding provider names.

    Returns:
        List of provider name strings available in the registry.
    """
    return list(_EMBEDDING_PROVIDER_REGISTRY.keys())


def create_embedding_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseEmbeddingProvider:
    """
    Create an embedding provider instance by name.

    Factory function that looks up the provider class in the registry
    and instantiates it with the provided configuration.

    Args:
        provider_name: Provider identifier ('openai' or 'ollama').
        api_key: API key for the provider. If None, reads from settings.
        model: Model identifier. If None, uses provider default.
        **kwargs: Additional provider-specific configuration.

    Returns:
        An initialized embedding provider instance.

    Raises:
        ValueError: If the provider name is not registered.
        EmbeddingError: If required configuration is missing.
    """
    if provider_name not in _EMBEDDING_PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown embedding provider: '{provider_name}'. "
            f"Available providers: {get_registered_embedding_providers()}"
        )

    provider_class = _EMBEDDING_PROVIDER_REGISTRY[provider_name]

    # Resolve api_key from settings if not provided
    if api_key is None and provider_name == "openai":
        api_key = settings.OPENAI_API_KEY

    # Raise EmbeddingError if api_key is missing for cloud providers
    if provider_name == "openai" and not api_key:
        raise EmbeddingError(
            message="OPENAI_API_KEY is required for the OpenAI embedding provider",
            provider=provider_name,
            retryable=False,
        )

    # Resolve model from settings if not provided
    if model is None:
        if provider_name == "openai":
            model = settings.OPENAI_EMBEDDING_MODEL
        elif provider_name == "ollama":
            model = settings.OLLAMA_EMBEDDING_MODEL

    # Build kwargs with provider-specific settings (only if not already provided)
    if provider_name == "openai":
        if "timeout" not in kwargs:
            kwargs["timeout"] = settings.OPENAI_TIMEOUT_SECONDS
        if "max_retries" not in kwargs:
            kwargs["max_retries"] = settings.OPENAI_MAX_RETRIES
        if "dimensions" not in kwargs:
            kwargs["dimensions"] = settings.EMBEDDING_DIMENSIONS
    elif provider_name == "ollama":
        if "base_url" not in kwargs:
            kwargs["base_url"] = settings.OLLAMA_BASE_URL
        if "timeout" not in kwargs:
            kwargs["timeout"] = settings.OLLAMA_TIMEOUT_SECONDS
        if "max_retries" not in kwargs:
            kwargs["max_retries"] = 3

    # Instantiate and return the provider
    # For openai, api_key is required; for others, pass api_key if provided
    if provider_name == "openai":
        return provider_class(api_key=api_key, model=model, **kwargs)
    elif provider_name == "ollama":
        return provider_class(model=model, **kwargs)
    else:
        # Generic provider - pass api_key and model if provided
        return provider_class(api_key=api_key, model=model, **kwargs)


# Auto-register providers on module import
def _auto_register() -> None:
    """
    Auto-register all known embedding providers.

    Called at module import time to populate the registry with
    OpenAIEmbeddingProvider and OllamaEmbeddingProvider.
    """
    try:
        from app.etl.embedding.providers.openai import OpenAIEmbeddingProvider
        register_embedding_provider("openai", OpenAIEmbeddingProvider)
    except ImportError as e:
        logger.warning("Could not register OpenAI embedding provider: %s", e)

    try:
        from app.etl.embedding.providers.ollama import OllamaEmbeddingProvider
        register_embedding_provider("ollama", OllamaEmbeddingProvider)
    except ImportError as e:
        logger.warning("Could not register Ollama embedding provider: %s", e)


_auto_register()
