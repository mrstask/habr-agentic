"""
Tests for app.services.settings_service — SettingsService configuration management.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import SettingsService
from app.schemas import (
    AppSettingsResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
    TranslationSettingsResponse,
    EmbeddingSettingsResponse,
    ContentFilterSettingsResponse,
)


# ---------------------------------------------------------------------------
# get_app_settings
# ---------------------------------------------------------------------------

def test_get_app_settings_returns_response():
    """get_app_settings returns AppSettingsResponse with current settings."""
    with patch("app.services.settings_service.settings") as mock_settings:
        mock_settings.APP_ENV = "development"
        mock_settings.APP_DEBUG = True
        mock_settings.CORS_ORIGINS = ["http://localhost:5173"]
        mock_settings.TRANSLATION_PROVIDER = "grok"
        mock_settings.EMBEDDING_PROVIDER = "openai"
        mock_settings.CONTENT_FILTER_PROVIDER = "ollama"

        service = SettingsService(AsyncMock(spec=AsyncSession))
        result = service.get_app_settings()

    assert isinstance(result, AppSettingsResponse)
    assert result.app_env == "development"
    assert result.app_debug is True
    assert result.cors_origins == ["http://localhost:5173"]
    assert result.translation_provider == "grok"
    assert result.embedding_provider == "openai"
    assert result.content_filter_provider == "ollama"


# ---------------------------------------------------------------------------
# get_agent_config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_agent_config_returns_list():
    """get_agent_config returns a list of AgentConfigResponse."""
    now = datetime.now(timezone.utc)
    config1 = MagicMock()
    config1.key = "AGENT_ENABLED"
    config1.value = "True"
    config1.updated_at = now

    config2 = MagicMock()
    config2.key = "AGENT_DRY_RUN"
    config2.value = "False"
    config2.updated_at = now

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [config1, config2]
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = SettingsService(mock_session)
    result = await service.get_agent_config()

    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], AgentConfigResponse)
    assert result[0].key == "AGENT_ENABLED"
    assert result[0].value == "True"
    assert result[1].key == "AGENT_DRY_RUN"


@pytest.mark.asyncio
async def test_get_agent_config_returns_empty_list():
    """get_agent_config returns empty list when no configs exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = SettingsService(mock_session)
    result = await service.get_agent_config()

    assert result == []


# ---------------------------------------------------------------------------
# update_agent_config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_agent_config_succeeds():
    """update_agent_config updates the value and returns AgentConfigResponse."""
    now = datetime.now(timezone.utc)
    config = MagicMock()
    config.key = "AGENT_ENABLED"
    config.value = "False"
    config.updated_at = now

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = config
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = SettingsService(mock_session)
    update_data = AgentConfigUpdate(value="True")

    result = await service.update_agent_config("AGENT_ENABLED", update_data)

    assert config.value == "True"
    assert isinstance(result, AgentConfigResponse)
    assert result.key == "AGENT_ENABLED"
    assert result.value == "True"


@pytest.mark.asyncio
async def test_update_agent_config_raises_404_not_found():
    """update_agent_config raises 404 when config key does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = SettingsService(mock_session)
    update_data = AgentConfigUpdate(value="True")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_agent_config("NONEXISTENT_KEY", update_data)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# get_translation_settings
# ---------------------------------------------------------------------------

def test_get_translation_settings_returns_response():
    """get_translation_settings returns TranslationSettingsResponse."""
    with patch("app.services.settings_service.settings") as mock_settings:
        mock_settings.TRANSLATION_PROVIDER = "grok"
        mock_settings.TRANSLATION_FALLBACK_ENABLED = True
        mock_settings.TRANSLATION_SOURCE_LANG = "ru"
        mock_settings.TRANSLATION_TARGET_LANG = "uk"
        mock_settings.OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"

        service = SettingsService(AsyncMock(spec=AsyncSession))
        result = service.get_translation_settings()

    assert isinstance(result, TranslationSettingsResponse)
    assert result.provider == "grok"
    assert result.fallback_enabled is True
    assert result.source_language == "ru"
    assert result.target_language == "uk"
    assert result.model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# get_embedding_settings
# ---------------------------------------------------------------------------

def test_get_embedding_settings_returns_response():
    """get_embedding_settings returns EmbeddingSettingsResponse."""
    with patch("app.services.settings_service.settings") as mock_settings:
        mock_settings.EMBEDDING_PROVIDER = "openai"
        mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
        mock_settings.EMBEDDING_DIMENSIONS = 1536

        service = SettingsService(AsyncMock(spec=AsyncSession))
        result = service.get_embedding_settings()

    assert isinstance(result, EmbeddingSettingsResponse)
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536


# ---------------------------------------------------------------------------
# get_content_filter_settings
# ---------------------------------------------------------------------------

def test_get_content_filter_settings_returns_response():
    """get_content_filter_settings returns ContentFilterSettingsResponse."""
    with patch("app.services.settings_service.settings") as mock_settings:
        mock_settings.CONTENT_FILTER_ENABLED = True
        mock_settings.CONTENT_FILTER_PROVIDER = "ollama"
        mock_settings.CONTENT_FILTER_REJECT_RUSSIA_SPECIFIC = True

        service = SettingsService(AsyncMock(spec=AsyncSession))
        result = service.get_content_filter_settings()

    assert isinstance(result, ContentFilterSettingsResponse)
    assert result.enabled is True
    assert result.provider == "ollama"
    assert result.reject_russia_specific is True
