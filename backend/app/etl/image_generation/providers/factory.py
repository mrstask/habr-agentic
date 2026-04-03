"""
Image generation provider factory and registry.

Provides a factory function to instantiate image generation providers based on
configuration, and a registry for managing available providers.

Usage::

    from app.etl.image_generation.providers.factory import create_image_provider
    from app.core.config import settings

    provider = create_image_provider(api_key=settings.OPENAI_API_KEY)
"""

import logging
from typing import Optional

from app.core.config import settings
from app.etl.image_generation.base import (
    BaseImageGenerationProvider,
    ImageGenerationError,
)

logger = logging.getLogger(__name__)

# Registry of available image generation provider classes
_IMAGE_PROVIDER_REGISTRY: dict[str, type[BaseImageGenerationProvider]] = {}


def register_image_provider(
    name: str,
    provider_class: type[BaseImageGenerationProvider],
) -> None:
    """
    Register an image generation provider class in the global registry.

    Args:
        name: Provider identifier (e.g., 'openai').
        provider_class: The provider class to register.
    """
    _IMAGE_PROVIDER_REGISTRY[name] = provider_class
    logger.info("Registered image generation provider: %s", name)


def get_registered_image_providers() -> list[str]:
    """
    Get a list of all registered image generation provider names.

    Returns:
        List of provider name strings available in the registry.
    """
    return list(_IMAGE_PROVIDER_REGISTRY.keys())


def create_image_provider(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseImageGenerationProvider:
    """
    Create an image generation provider instance.

    Factory function that looks up the provider class in the registry
    and instantiates it with the provided configuration.

    Args:
        api_key: API key for the provider. If None, reads from settings.
        model: Model identifier. If None, uses settings default.
        **kwargs: Additional provider-specific configuration.

    Returns:
        An initialized image generation provider instance.

    Raises:
        ValueError: If no provider is registered.
        ImageGenerationError: If required configuration is missing.
    """
    # Resolve api_key from settings if not provided
    if api_key is None:
        api_key = settings.OPENAI_API_KEY

    if not api_key:
        raise ImageGenerationError(
            message="OpenAI API key is required for image generation",
            provider="openai",
            retryable=False,
        )

    # Resolve model from settings if not provided
    if model is None:
        model = settings.IMAGE_GENERATION_MODEL

    # Build kwargs with provider-specific settings
    if "timeout" not in kwargs:
        kwargs["timeout"] = settings.OPENAI_TIMEOUT_SECONDS
    if "max_retries" not in kwargs:
        kwargs["max_retries"] = settings.OPENAI_MAX_RETRIES

    # Look up provider class in registry (default to 'openai')
    provider_name = kwargs.pop("provider_name", "openai")
    provider_class = _IMAGE_PROVIDER_REGISTRY.get(provider_name)

    if provider_class is None:
        raise ValueError(
            f"Unknown image generation provider: '{provider_name}'. "
            f"Available: {list(_IMAGE_PROVIDER_REGISTRY.keys())}"
        )

    # Instantiate and return the provider
    return provider_class(api_key=api_key, model=model, **kwargs)


# Auto-register providers on module import
def _auto_register() -> None:
    """
    Auto-register all known image generation providers.

    Called at module import time to populate the registry with
    OpenAIImageGenerationProvider.
    """
    try:
        from app.etl.image_generation.providers.openai import (
            OpenAIImageGenerationProvider,
        )

        register_image_provider("openai", OpenAIImageGenerationProvider)
    except ImportError:
        logger.warning("OpenAIImageGenerationProvider not available, skipping registration")


_auto_register()
