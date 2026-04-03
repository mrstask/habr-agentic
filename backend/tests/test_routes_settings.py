"""
Tests for app.api.routes.settings — Settings and configuration API routes.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.settings import router as settings_router
from app.schemas import (
    AppSettingsResponse,
    AgentConfigResponse,
    TranslationSettingsResponse,
    EmbeddingSettingsResponse,
    ContentFilterSettingsResponse,
)


@pytest.fixture
def app():
    """Create a FastAPI app with the settings router."""
    app = FastAPI()
    app.include_router(settings_router)
    return app


@pytest.fixture
def client(app):
    """Create a TestClient for the settings router."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# get_app_settings
# ---------------------------------------------------------------------------

def test_get_app_settings_returns_200(client):
    """GET /settings/app returns 200 with application settings."""
    with patch("app.api.routes.settings.SettingsService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_app_settings.return_value = AppSettingsResponse(
            app_env="development",
            app_debug=True,
            cors_origins=["http://localhost:5173"],
            translation_provider="grok",
            embedding_provider="openai",
            content_filter_provider="ollama",
        )
        mock_service_cls.return_value = mock_service

        response = client.get("/settings/app")

    assert response.status_code == 200
    data = response.json()
    assert data["app_env"] == "development"
    assert data["app_debug"] is True
    assert data["translation_provider"] == "grok"


# ---------------------------------------------------------------------------
# get_agent_config
# ---------------------------------------------------------------------------

def test_get_agent_config_returns_200(client):
    """GET /settings/agent returns 200 with agent configuration list."""
    now = datetime.now(timezone.utc).isoformat()

    mock_service = MagicMock()
    mock_service.get_agent_config = AsyncMock(
        return_value=[
            AgentConfigResponse(
                key="AGENT_ENABLED",
                value="True",
                description=None,
                updated_at=now,
            ),
            AgentConfigResponse(
                key="AGENT_DRY_RUN",
                value="False",
                description=None,
                updated_at=now,
            ),
        ]
    )

    with patch("app.api.routes.settings.SettingsService", return_value=mock_service):
        response = client.get("/settings/agent")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["key"] == "AGENT_ENABLED"
    assert data[0]["value"] == "True"


def test_get_agent_config_returns_empty_list(client):
    """GET /settings/agent returns empty list when no configs exist."""
    mock_service = MagicMock()
    mock_service.get_agent_config = AsyncMock(return_value=[])

    with patch("app.api.routes.settings.SettingsService", return_value=mock_service):
        response = client.get("/settings/agent")

    assert response.status_code == 200
    data = response.json()
    assert data == []


# ---------------------------------------------------------------------------
# update_agent_config
# ---------------------------------------------------------------------------

def test_update_agent_config_returns_200(client):
    """PUT /settings/agent/{key} returns 200 with updated config."""
    now = datetime.now(timezone.utc).isoformat()

    mock_service = MagicMock()
    mock_service.update_agent_config = AsyncMock(
        return_value=AgentConfigResponse(
            key="AGENT_ENABLED",
            value="False",
            description=None,
            updated_at=now,
        )
    )

    with patch("app.api.routes.settings.SettingsService", return_value=mock_service):
        response = client.put(
            "/settings/agent/AGENT_ENABLED",
            json={"value": "False"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "AGENT_ENABLED"
    assert data["value"] == "False"


def test_update_agent_config_returns_404(client):
    """PUT /settings/agent/{key} returns 404 when key not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.update_agent_config = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent configuration key 'NONEXISTENT' not found",
        )
    )

    with patch("app.api.routes.settings.SettingsService", return_value=mock_service):
        response = client.put(
            "/settings/agent/NONEXISTENT",
            json={"value": "True"},
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# get_translation_settings
# ---------------------------------------------------------------------------

def test_get_translation_settings_returns_200(client):
    """GET /settings/translation returns 200 with translation settings."""
    with patch("app.api.routes.settings.SettingsService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_translation_settings.return_value = TranslationSettingsResponse(
            provider="grok",
            fallback_enabled=True,
            source_language="ru",
            target_language="uk",
            model="gpt-4o-mini",
        )
        mock_service_cls.return_value = mock_service

        response = client.get("/settings/translation")

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "grok"
    assert data["fallback_enabled"] is True
    assert data["source_language"] == "ru"
    assert data["target_language"] == "uk"


# ---------------------------------------------------------------------------
# get_embedding_settings
# ---------------------------------------------------------------------------

def test_get_embedding_settings_returns_200(client):
    """GET /settings/embedding returns 200 with embedding settings."""
    with patch("app.api.routes.settings.SettingsService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_embedding_settings.return_value = EmbeddingSettingsResponse(
            provider="openai",
            model="text-embedding-3-small",
            dimensions=1536,
        )
        mock_service_cls.return_value = mock_service

        response = client.get("/settings/embedding")

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["model"] == "text-embedding-3-small"
    assert data["dimensions"] == 1536


# ---------------------------------------------------------------------------
# get_content_filter_settings
# ---------------------------------------------------------------------------

def test_get_content_filter_settings_returns_200(client):
    """GET /settings/content-filter returns 200 with content filter settings."""
    with patch("app.api.routes.settings.SettingsService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_content_filter_settings.return_value = ContentFilterSettingsResponse(
            enabled=True,
            provider="ollama",
            reject_russia_specific=True,
        )
        mock_service_cls.return_value = mock_service

        response = client.get("/settings/content-filter")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider"] == "ollama"
    assert data["reject_russia_specific"] is True
