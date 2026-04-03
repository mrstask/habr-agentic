"""
Image generation provider implementations.

Contains concrete image generation provider classes and the factory
for instantiating them based on configuration.

Submodules:
    openai: OpenAI DALL-E image generation provider.
    factory: Provider factory and registry.
"""

from app.etl.image_generation.providers.openai import OpenAIImageGenerationProvider
from app.etl.image_generation.providers.factory import (
    create_image_provider,
    register_image_provider,
    get_registered_image_providers,
)

__all__ = [
    "OpenAIImageGenerationProvider",
    "create_image_provider",
    "register_image_provider",
    "get_registered_image_providers",
]
