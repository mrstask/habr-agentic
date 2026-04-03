"""
Settings and configuration management service.

Provides business logic for reading application settings (from
environment variables) and managing agent configuration (persisted
to the database).
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.schemas import (
    AppSettingsResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
    TranslationSettingsResponse,
    EmbeddingSettingsResponse,
    ContentFilterSettingsResponse,
)


class SettingsService:
    """
    Service layer for application and agent configuration management.

    Reads static application settings from the Settings singleton
    and manages dynamic agent configuration stored in the database.

    Args:
        session: Async SQLAlchemy session for the App database. Can be None
                 for methods that only read from environment variables.
    """

    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        """
        Initialize the SettingsService with an optional database session.

        Args:
            session: Async SQLAlchemy session for the App database.
                     Can be None for read-only settings methods.
        """
        self.session = session

    def get_app_settings(self) -> AppSettingsResponse:
        """
        Get application settings (read-only, from environment variables).

        Returns:
            AppSettingsResponse: Application configuration settings.
        """
        return AppSettingsResponse(
            app_env=settings.APP_ENV,
            app_debug=settings.APP_DEBUG,
            cors_origins=settings.CORS_ORIGINS,
            translation_provider=settings.TRANSLATION_PROVIDER,
            embedding_provider=settings.EMBEDDING_PROVIDER,
            content_filter_provider=settings.CONTENT_FILTER_PROVIDER,
        )

    async def get_agent_config(self) -> list[AgentConfigResponse]:
        """
        Get all agent configuration entries from the database.

        Returns:
            list[AgentConfigResponse]: Agent configuration key-value pairs.

        Raises:
            ValueError: If no database session is available.
        """
        if self.session is None:
            raise ValueError("Database session required for get_agent_config")

        from app.models.pipeline import AgentConfig

        result = await self.session.execute(select(AgentConfig))
        configs = result.scalars().all()

        return [
            AgentConfigResponse(
                key=c.key,
                value=c.value,
                description=None,
                updated_at=c.updated_at,
            )
            for c in configs
        ]

    async def update_agent_config(
        self, key: str, update_data: AgentConfigUpdate
    ) -> AgentConfigResponse:
        """
        Update a specific agent configuration value.

        Args:
            key: Configuration key to update.
            update_data: New configuration value.

        Returns:
            AgentConfigResponse: Updated configuration.

        Raises:
            HTTPException: 404 Not Found if configuration key does not exist.
            ValueError: If no database session is available.
        """
        if self.session is None:
            raise ValueError("Database session required for update_agent_config")

        from app.models.pipeline import AgentConfig

        result = await self.session.execute(
            select(AgentConfig).where(AgentConfig.key == key)
        )
        config = result.scalar_one_or_none()

        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent configuration key '{key}' not found",
            )

        # Update the value field
        config.value = update_data.value
        await self.session.flush()
        await self.session.refresh(config)

        return AgentConfigResponse(
            key=config.key,
            value=config.value,
            description=None,
            updated_at=config.updated_at,
        )

    def get_translation_settings(self) -> TranslationSettingsResponse:
        """
        Get translation provider settings from application configuration.

        Returns:
            TranslationSettingsResponse: Translation configuration including
                                         provider, model, and language settings.
        """
        return TranslationSettingsResponse(
            provider=settings.TRANSLATION_PROVIDER,
            fallback_enabled=settings.TRANSLATION_FALLBACK_ENABLED,
            source_language=settings.TRANSLATION_SOURCE_LANG,
            target_language=settings.TRANSLATION_TARGET_LANG,
            model=settings.OPENAI_TRANSLATION_MODEL,
        )

    def get_embedding_settings(self) -> EmbeddingSettingsResponse:
        """
        Get embedding provider settings from application configuration.

        Returns:
            EmbeddingSettingsResponse: Embedding configuration including
                                       provider and model settings.
        """
        return EmbeddingSettingsResponse(
            provider=settings.EMBEDDING_PROVIDER,
            model=settings.OPENAI_EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )

    def get_content_filter_settings(self) -> ContentFilterSettingsResponse:
        """
        Get content filter settings from application configuration.

        Returns:
            ContentFilterSettingsResponse: Content filter configuration including
                                          provider and rejection rules.
        """
        return ContentFilterSettingsResponse(
            enabled=settings.CONTENT_FILTER_ENABLED,
            provider=settings.CONTENT_FILTER_PROVIDER,
            reject_russia_specific=settings.CONTENT_FILTER_REJECT_RUSSIA_SPECIFIC,
        )
