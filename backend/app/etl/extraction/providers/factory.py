"""
Extraction provider factory and registry.

Provides a factory function to instantiate extraction providers based on
configuration, and a registry for managing available providers.

Usage::

    from app.etl.extraction.providers.factory import create_extraction_provider
    from app.core.config import settings

    provider = create_extraction_provider(settings.EXTRACTION_PROVIDER)
"""

import logging

from app.etl.extraction.base import BaseExtractionProvider

logger = logging.getLogger(__name__)

# Registry of available extraction provider classes
_EXTRACTION_PROVIDER_REGISTRY: dict[str, type[BaseExtractionProvider]] = {}


def register_extraction_provider(
    name: str,
    provider_class: type[BaseExtractionProvider],
) -> None:
    """
    Register an extraction provider class in the global registry.

    Args:
        name: Provider identifier (e.g., 'html', 'rss').
        provider_class: The provider class to register.
    """
    _EXTRACTION_PROVIDER_REGISTRY[name] = provider_class
    logger.info("Registered extraction provider: %s", name)


def get_registered_extraction_providers() -> list[str]:
    """
    Get a list of all registered extraction provider names.

    Returns:
        List of provider name strings available in the registry.
    """
    return list(_EXTRACTION_PROVIDER_REGISTRY.keys())


def create_extraction_provider(
    provider_name: str,
    **kwargs,
) -> BaseExtractionProvider:
    """
    Create an extraction provider instance by name.

    Factory function that looks up the provider class in the registry
    and instantiates it with the provided configuration.

    Args:
        provider_name: Provider identifier (e.g., 'html', 'rss').
        **kwargs: Additional provider-specific configuration
                  (timeout, max_retries, user_agent, etc.).

    Returns:
        An initialized extraction provider instance.

    Raises:
        ValueError: If the provider name is not registered.
        ExtractionError: If required configuration is missing.
    """
    # Look up provider_name in _EXTRACTION_PROVIDER_REGISTRY
    provider_class = _EXTRACTION_PROVIDER_REGISTRY.get(provider_name)
    if provider_class is None:
        raise ValueError(
            f"Unknown extraction provider: '{provider_name}'. "
            f"Available providers: {get_registered_extraction_providers()}"
        )

    # Build provider_kwargs with defaults
    provider_kwargs: dict = {}

    # Use explicitly passed kwargs or fall back to defaults
    if "timeout" not in kwargs:
        provider_kwargs["timeout"] = 30
    if "max_retries" not in kwargs:
        provider_kwargs["max_retries"] = 3
    if "user_agent" not in kwargs:
        provider_kwargs["user_agent"] = "HabrAgenticPipeline/1.0"

    # Merge with explicitly passed kwargs (they take precedence)
    provider_kwargs.update(kwargs)

    # Instantiate and return the provider class
    return provider_class(**provider_kwargs)


# Auto-register providers on module import
def _auto_register() -> None:
    """
    Auto-register all known extraction providers.

    Called at module import time to populate the registry with
    HtmlExtractionProvider and RssExtractionProvider.
    """
    # Import HtmlExtractionProvider and register as 'html'
    try:
        from app.etl.extraction.providers.html import HtmlExtractionProvider

        register_extraction_provider("html", HtmlExtractionProvider)
    except ImportError as e:
        logger.warning("Failed to register HtmlExtractionProvider: %s", e)

    # Import RssExtractionProvider and register as 'rss'
    try:
        from app.etl.extraction.providers.rss import RssExtractionProvider

        register_extraction_provider("rss", RssExtractionProvider)
    except ImportError as e:
        logger.warning("Failed to register RssExtractionProvider: %s", e)


_auto_register()
