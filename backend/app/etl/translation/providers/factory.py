"""
Translation provider factory and registry.

Provides a factory function to instantiate translation providers based on
configuration, and a registry for managing available providers.

Usage::

    from app.etl.translation.providers.factory import create_provider
    from app.core.config import settings

    provider = create_provider(settings.TRANSLATION_PROVIDER)
"""

import logging
from typing import Optional

from app.etl.translation.base import BaseTranslationProvider, TranslationError

logger = logging.getLogger(__name__)

# Registry of available provider classes
_PROVIDER_REGISTRY: dict[str, type[BaseTranslationProvider]] = {}


def register_provider(name: str, provider_class: type[BaseTranslationProvider]) -> None:
    """
    Register a translation provider class in the global registry.

    Args:
        name: Provider identifier (e.g., 'grok', 'openai').
        provider_class: The provider class to register.
    """
    _PROVIDER_REGISTRY[name] = provider_class
    logger.debug("Registered translation provider: %s -> %s", name, provider_class.__name__)


def get_registered_providers() -> list[str]:
    """
    Get a list of all registered provider names.

    Returns:
        List of provider name strings available in the registry.
    """
    return list(_PROVIDER_REGISTRY.keys())


def create_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseTranslationProvider:
    """
    Create a translation provider instance by name.

    Factory function that looks up the provider class in the registry
    and instantiates it with the provided configuration.

    Args:
        provider_name: Provider identifier ('grok' or 'openai').
        api_key: API key for the provider. If None, reads from settings.
        model: Model identifier. If None, uses provider default.
        **kwargs: Additional provider-specific configuration.

    Returns:
        An initialized translation provider instance.

    Raises:
        ValueError: If the provider name is not registered.
        TranslationError: If required configuration is missing.
    """
    if provider_name not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown translation provider: '{provider_name}'. "
            f"Available providers: {available}"
        )

    # Resolve api_key from settings if not provided
    if api_key is None:
        from app.core.config import settings

        if provider_name == "grok":
            api_key = settings.GROK_API_KEY
        elif provider_name == "openai":
            api_key = settings.OPENAI_API_KEY

    if not api_key:
        raise TranslationError(
            message=f"API key not provided and not found in settings for provider '{provider_name}'",
            provider=provider_name,
            retryable=False,
        )

    # Resolve model from settings if not provided
    if model is None:
        from app.core.config import settings

        if provider_name == "grok":
            model = settings.GROK_TRANSLATION_MODEL
        elif provider_name == "openai":
            model = settings.OPENAI_TRANSLATION_MODEL

    provider_class = _PROVIDER_REGISTRY[provider_name]

    # Build kwargs with provider-specific settings
    if provider_name == "grok":
        from app.core.config import settings

        kwargs.setdefault("base_url", settings.GROK_BASE_URL)
        kwargs.setdefault("timeout", settings.GROK_TIMEOUT_SECONDS)
        kwargs.setdefault("max_retries", settings.GROK_MAX_RETRIES)
    elif provider_name == "openai":
        from app.core.config import settings

        kwargs.setdefault("timeout", settings.OPENAI_TIMEOUT_SECONDS)
        kwargs.setdefault("max_retries", settings.OPENAI_MAX_RETRIES)

    logger.info(
        "Creating translation provider: %s (model: %s)",
        provider_name,
        model,
    )

    return provider_class(api_key=api_key, model=model, **kwargs)


def create_fallback_provider(
    primary_name: str,
    **kwargs,
) -> Optional[BaseTranslationProvider]:
    """
    Create a fallback provider different from the primary.

    When the primary provider fails, this creates an instance of the
    secondary provider for fallback translation attempts.

    Args:
        primary_name: Name of the primary provider (to avoid using the same one).
        **kwargs: Additional configuration for the fallback provider.

    Returns:
        A fallback provider instance, or None if no fallback is available.
    """
    # Determine fallback provider name (grok <-> openai)
    fallback_map = {
        "grok": "openai",
        "openai": "grok",
    }

    fallback_name = fallback_map.get(primary_name)

    if fallback_name is None or fallback_name == primary_name:
        logger.warning(
            "No fallback provider available for primary: %s",
            primary_name,
        )
        return None

    if fallback_name not in _PROVIDER_REGISTRY:
        logger.warning(
            "Fallback provider '%s' is not registered, cannot create fallback",
            fallback_name,
        )
        return None

    try:
        return create_provider(fallback_name, **kwargs)
    except (ValueError, TranslationError) as exc:
        logger.warning("Failed to create fallback provider '%s': %s", fallback_name, exc)
        return None


# Auto-register providers on module import
def _auto_register() -> None:
    """
    Auto-register all known translation providers.

    Called at module import time to populate the registry with
    GrokTranslationProvider and OpenAITranslationProvider.
    """
    try:
        from app.etl.translation.providers.grok import GrokTranslationProvider

        register_provider("grok", GrokTranslationProvider)
    except ImportError as exc:
        logger.warning("Failed to register GrokTranslationProvider: %s", exc)

    try:
        from app.etl.translation.providers.openai import OpenAITranslationProvider

        register_provider("openai", OpenAITranslationProvider)
    except ImportError as exc:
        logger.warning("Failed to register OpenAITranslationProvider: %s", exc)


_auto_register()
