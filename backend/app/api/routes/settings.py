"""
Settings and configuration API routes.

Provides endpoints for managing application settings and agent configuration.
Application settings are read-only (from environment variables), while agent
configuration can be updated at runtime and is persisted to the database.

All endpoints use the SettingsService for business logic and the
centralized database session dependency from app.dependencies.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_app_session
from app.schemas import (
    AppSettingsResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
    TranslationSettingsResponse,
    EmbeddingSettingsResponse,
    ContentFilterSettingsResponse,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "/app",
    response_model=AppSettingsResponse,
    summary="Get application settings",
)
async def get_app_settings() -> AppSettingsResponse:
    """
    Get application settings (read-only).

    These settings are loaded from environment variables at startup
    and cannot be changed at runtime.

    Returns:
        AppSettingsResponse: Application configuration settings.
    """
    service = SettingsService(None)  # type: ignore[arg-type]
    return service.get_app_settings()


@router.get(
    "/agent",
    response_model=list[AgentConfigResponse],
    summary="Get agent configuration",
)
async def get_agent_config(
    session: AsyncSession = Depends(get_app_session),
) -> list[AgentConfigResponse]:
    """
    Get agent configuration from database.

    Returns:
        list[AgentConfigResponse]: Agent configuration key-value pairs.
    """
    service = SettingsService(session)
    return await service.get_agent_config()


@router.put(
    "/agent/{key}",
    response_model=AgentConfigResponse,
    summary="Update agent configuration",
)
async def update_agent_config(
    key: str,
    update_data: AgentConfigUpdate,
    session: AsyncSession = Depends(get_app_session),
) -> AgentConfigResponse:
    """
    Update agent configuration value.

    Args:
        key: Configuration key to update.
        update_data: New configuration value.
        session: Async database session.

    Returns:
        AgentConfigResponse: Updated configuration.

    Raises:
        HTTPException: 404 Not Found if configuration key does not exist.
    """
    service = SettingsService(session)
    return await service.update_agent_config(key, update_data)


@router.get(
    "/translation",
    response_model=TranslationSettingsResponse,
    summary="Get translation settings",
)
async def get_translation_settings() -> TranslationSettingsResponse:
    """
    Get translation provider settings.

    Returns:
        TranslationSettingsResponse: Translation configuration including
                                     provider, model, and language settings.
    """
    service = SettingsService(None)  # type: ignore[arg-type]
    return service.get_translation_settings()


@router.get(
    "/embedding",
    response_model=EmbeddingSettingsResponse,
    summary="Get embedding settings",
)
async def get_embedding_settings() -> EmbeddingSettingsResponse:
    """
    Get embedding provider settings.

    Returns:
        EmbeddingSettingsResponse: Embedding configuration including
                                   provider and model settings.
    """
    service = SettingsService(None)  # type: ignore[arg-type]
    return service.get_embedding_settings()


@router.get(
    "/content-filter",
    response_model=ContentFilterSettingsResponse,
    summary="Get content filter settings",
)
async def get_content_filter_settings() -> ContentFilterSettingsResponse:
    """
    Get content filter settings.

    Returns:
        ContentFilterSettingsResponse: Content filter configuration including
                                      provider and rejection rules.
    """
    service = SettingsService(None)  # type: ignore[arg-type]
    return service.get_content_filter_settings()
