"""
Image generation ETL module.

Provides image generation provider abstractions, concrete implementations,
and factory functions for the Habr Agentic Pipeline.

Submodules:
    base: Abstract base class and shared data types.
    providers: Concrete provider implementations (OpenAI DALL-E).
"""

from app.etl.image_generation.base import (
    BaseImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageGenerationError,
)
from app.etl.image_generation.providers.factory import (
    create_image_provider,
    register_image_provider,
    get_registered_image_providers,
)

__all__ = [
    "BaseImageGenerationProvider",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "ImageGenerationError",
    "create_image_provider",
    "register_image_provider",
    "get_registered_image_providers",
]
