"""
Extraction ETL module.

Provides extraction provider abstractions, concrete implementations,
and factory functions for the Habr Agentic Pipeline.

Submodules:
    base: Abstract base class and shared data types.
    providers: Concrete provider implementations (HTML, RSS).
"""

from app.etl.extraction.base import (
    BaseExtractionProvider,
    ExtractionRequest,
    ExtractionResult,
    ExtractionError,
)
from app.etl.extraction.providers.factory import (
    create_extraction_provider,
    register_extraction_provider,
    get_registered_extraction_providers,
)

__all__ = [
    "BaseExtractionProvider",
    "ExtractionRequest",
    "ExtractionResult",
    "ExtractionError",
    "create_extraction_provider",
    "register_extraction_provider",
    "get_registered_extraction_providers",
]
