"""
Extraction provider implementations.

Contains concrete extraction providers (HTML parser, RSS feed reader)
and the factory/registry for instantiating them.
"""

from app.etl.extraction.providers.factory import (
    create_extraction_provider,
    register_extraction_provider,
    get_registered_extraction_providers,
)

__all__ = [
    "create_extraction_provider",
    "register_extraction_provider",
    "get_registered_extraction_providers",
]
