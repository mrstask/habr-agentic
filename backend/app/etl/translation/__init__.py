"""
Translation ETL module.

Provides translation provider abstractions, concrete implementations,
prompt templates, and factory functions for the Habr Agentic Pipeline.

Submodules:
    base: Abstract base class and shared data types.
    providers: Concrete provider implementations (Grok, OpenAI).
    prompts: Prompt template loading and formatting.
"""

from app.etl.translation.base import (
    BaseTranslationProvider,
    TranslationRequest,
    TranslationResult,
    ProofreadingResult,
    TranslationError,
)
from app.etl.translation.providers.factory import (
    create_provider,
    create_fallback_provider,
    register_provider,
    get_registered_providers,
)

__all__ = [
    "BaseTranslationProvider",
    "TranslationRequest",
    "TranslationResult",
    "ProofreadingResult",
    "TranslationError",
    "create_provider",
    "create_fallback_provider",
    "register_provider",
    "get_registered_providers",
]
