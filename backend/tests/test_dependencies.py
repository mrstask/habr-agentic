"""
Tests for app.dependencies — database session, authentication, and authorization dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_app_session,
    get_articles_session,
    get_optional_admin_token,
    get_required_admin_token,
    verify_admin_token,
    require_active_admin,
    require_superuser,
    get_pipeline_config,
    verify_pipeline_enabled,
    security,
)


# ---------------------------------------------------------------------------
# Database session dependencies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_app_session_yields_session():
    """get_app_session yields an AsyncSession and commits on success."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.dependencies.AppSessionLocal") as mock_local:
        mock_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_local.return_value.__aexit__ = AsyncMock(return_value=False)

        gen = get_app_session()
        session = await gen.__anext__()
        assert session is mock_session

        # Simulate normal exit (commit)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_app_session_rollback_on_error():
    """get_app_session rolls back when an exception occurs."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.dependencies.AppSessionLocal") as mock_local:
        mock_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_local.return_value.__aexit__ = AsyncMock(return_value=False)

        gen = get_app_session()
        session = await gen.__anext__()
        assert session is mock_session

        # Simulate exception after yield
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("db error"))

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_articles_session_yields_session():
    """get_articles_session yields an AsyncSession and commits on success."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.dependencies.ArticlesSessionLocal") as mock_local:
        mock_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_local.return_value.__aexit__ = AsyncMock(return_value=False)

        gen = get_articles_session()
        session = await gen.__anext__()
        assert session is mock_session

        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_articles_session_rollback_on_error():
    """get_articles_session rolls back when an exception occurs."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.dependencies.ArticlesSessionLocal") as mock_local:
        mock_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_local.return_value.__aexit__ = AsyncMock(return_value=False)

        gen = get_articles_session()
        session = await gen.__anext__()
        assert session is mock_session

        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("articles db error"))

        mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

def test_security_is_http_bearer_with_auto_error_false():
    """The security scheme should be HTTPBearer with auto_error=False."""
    assert security.auto_error is False


@pytest.mark.asyncio
async def test_get_optional_admin_token_returns_none_when_no_credentials():
    """get_optional_admin_token returns None when no credentials provided."""
    result = await get_optional_admin_token(credentials=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_optional_admin_token_returns_token_string():
    """get_optional_admin_token returns the token string when credentials exist."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="my-jwt-token")
    result = await get_optional_admin_token(credentials=creds)
    assert result == "my-jwt-token"


@pytest.mark.asyncio
async def test_get_required_admin_token_returns_token_string():
    """get_required_admin_token returns the token string when credentials exist."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="my-jwt-token")
    result = await get_required_admin_token(credentials=creds)
    assert result == "my-jwt-token"


@pytest.mark.asyncio
async def test_get_required_admin_token_raises_401_when_no_credentials():
    """get_required_admin_token raises 401 when credentials are None."""
    with pytest.raises(HTTPException) as exc_info:
        await get_required_admin_token(credentials=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Not authenticated"
    assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# verify_admin_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_admin_token_returns_user_info():
    """verify_admin_token decodes token and returns admin user dict."""
    mock_payload = {"sub": "1", "exp": 9999999999}
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.is_active = True

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.dependencies.AdminService.decode_access_token", return_value=mock_payload):
        result = await verify_admin_token(token="valid-token", session=mock_session)

    assert result["id"] == 1
    assert result["username"] == "admin"
    assert result["is_active"] is True


@pytest.mark.asyncio
async def test_verify_admin_token_raises_401_missing_subject():
    """verify_admin_token raises 401 when token payload has no 'sub'."""
    mock_payload = {"exp": 9999999999}
    mock_session = AsyncMock(spec=AsyncSession)

    with patch("app.dependencies.AdminService.decode_access_token", return_value=mock_payload):
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin_token(token="bad-token", session=mock_session)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "missing subject" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_admin_token_raises_401_user_not_found():
    """verify_admin_token raises 401 when user does not exist in DB."""
    mock_payload = {"sub": "999"}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.dependencies.AdminService.decode_access_token", return_value=mock_payload):
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin_token(token="valid-token", session=mock_session)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_verify_admin_token_raises_403_inactive_user():
    """verify_admin_token raises 403 when user account is inactive."""
    mock_payload = {"sub": "1"}
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.is_active = False

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.dependencies.AdminService.decode_access_token", return_value=mock_payload):
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin_token(token="valid-token", session=mock_session)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Inactive user account"


# ---------------------------------------------------------------------------
# require_active_admin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_active_admin_returns_admin_when_active():
    """require_active_admin returns admin dict when user is active."""
    admin = {"id": 1, "username": "admin", "is_active": True}
    result = await require_active_admin(admin=admin)
    assert result == admin


@pytest.mark.asyncio
async def test_require_active_admin_raises_403_when_inactive():
    """require_active_admin raises 403 when user is inactive."""
    admin = {"id": 1, "username": "admin", "is_active": False}
    with pytest.raises(HTTPException) as exc_info:
        await require_active_admin(admin=admin)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Inactive user account"


# ---------------------------------------------------------------------------
# require_superuser
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_superuser_returns_admin_when_only_one_admin():
    """require_superuser returns admin when there's only one admin in DB."""
    admin = {"id": 1, "username": "admin", "is_active": True}
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await require_superuser(admin=admin, session=mock_session)
    assert result == admin


@pytest.mark.asyncio
async def test_require_superuser_returns_admin_when_first_admin():
    """require_superuser returns admin when they are the first (lowest ID) admin."""
    admin = {"id": 1, "username": "admin", "is_active": True}
    mock_session = AsyncMock(spec=AsyncSession)

    # First call: count = 3
    # Second call: first admin has id=1
    mock_first_admin = MagicMock()
    mock_first_admin.id = 1

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar.return_value = 3
        else:
            mock_result.scalar_one_or_none.return_value = mock_first_admin
        return mock_result

    mock_session.execute = mock_execute

    result = await require_superuser(admin=admin, session=mock_session)
    assert result == admin


@pytest.mark.asyncio
async def test_require_superuser_raises_403_when_not_first_admin():
    """require_superuser raises 403 when admin is not the first created."""
    admin = {"id": 2, "username": "admin2", "is_active": True}
    mock_session = AsyncMock(spec=AsyncSession)

    mock_first_admin = MagicMock()
    mock_first_admin.id = 1

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar.return_value = 3
        else:
            mock_result.scalar_one_or_none.return_value = mock_first_admin
        return mock_result

    mock_session.execute = mock_execute

    with pytest.raises(HTTPException) as exc_info:
        await require_superuser(admin=admin, session=mock_session)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Superuser privileges required" in exc_info.value.detail


# ---------------------------------------------------------------------------
# get_pipeline_config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pipeline_config_returns_merged_config():
    """get_pipeline_config returns DB config merged with defaults."""
    mock_config = MagicMock()
    mock_config.key = "AGENT_ENABLED"
    mock_config.value = "True"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_config]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.AGENT_ENABLED = True
        mock_settings.AGENT_DRY_RUN = False
        mock_settings.AGENT_AUTO_PUBLISH = False
        mock_settings.AGENT_QUALITY_THRESHOLD = 5.0
        mock_settings.AGENT_POLL_INTERVAL_SECONDS = 3600
        mock_settings.AGENT_MAX_CONCURRENT_RUNS = 3

        result = await get_pipeline_config(session=mock_session)

    assert result["AGENT_ENABLED"] == "True"
    assert "AGENT_DRY_RUN" in result
    assert "AGENT_AUTO_PUBLISH" in result


@pytest.mark.asyncio
async def test_get_pipeline_config_uses_defaults_for_missing_keys():
    """get_pipeline_config fills in defaults for keys not in DB."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.AGENT_ENABLED = True
        mock_settings.AGENT_DRY_RUN = False
        mock_settings.AGENT_AUTO_PUBLISH = False
        mock_settings.AGENT_QUALITY_THRESHOLD = 5.0
        mock_settings.AGENT_POLL_INTERVAL_SECONDS = 3600
        mock_settings.AGENT_MAX_CONCURRENT_RUNS = 3

        result = await get_pipeline_config(session=mock_session)

    assert result["AGENT_ENABLED"] == "True"
    assert result["AGENT_DRY_RUN"] == "False"


# ---------------------------------------------------------------------------
# verify_pipeline_enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_pipeline_enabled_passes_when_enabled():
    """verify_pipeline_enabled returns config when pipeline is enabled."""
    config = {"AGENT_ENABLED": "True"}
    result = await verify_pipeline_enabled(config=config)
    assert result == config


@pytest.mark.asyncio
async def test_verify_pipeline_enabled_passes_when_enabled_numeric():
    """verify_pipeline_enabled passes when AGENT_ENABLED is '1'."""
    config = {"AGENT_ENABLED": "1"}
    result = await verify_pipeline_enabled(config=config)
    assert result == config


@pytest.mark.asyncio
async def test_verify_pipeline_enabled_passes_when_enabled_yes():
    """verify_pipeline_enabled passes when AGENT_ENABLED is 'yes'."""
    config = {"AGENT_ENABLED": "yes"}
    result = await verify_pipeline_enabled(config=config)
    assert result == config


@pytest.mark.asyncio
async def test_verify_pipeline_enabled_raises_400_when_disabled():
    """verify_pipeline_enabled raises 400 when pipeline is disabled."""
    config = {"AGENT_ENABLED": "False"}
    with pytest.raises(HTTPException) as exc_info:
        await verify_pipeline_enabled(config=config)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "disabled" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_verify_pipeline_enabled_raises_400_when_zero():
    """verify_pipeline_enabled raises 400 when AGENT_ENABLED is '0'."""
    config = {"AGENT_ENABLED": "0"}
    with pytest.raises(HTTPException) as exc_info:
        await verify_pipeline_enabled(config=config)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
