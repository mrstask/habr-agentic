"""
Tests for app.services.admin_service — AdminService authentication and user management.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin_service import AdminService
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminUserResponse,
    AdminUserCreate,
    AdminUserUpdate,
)
from app.core.config import settings


# ---------------------------------------------------------------------------
# create_access_token / decode_access_token (static methods)
# ---------------------------------------------------------------------------

def test_create_access_token_returns_string():
    """create_access_token returns a JWT token string."""
    token = AdminService.create_access_token(subject="1", expires_delta=3600)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_with_default_expiry():
    """create_access_token uses default expiry when expires_delta is None."""
    token = AdminService.create_access_token(subject="1")
    assert isinstance(token, str)


def test_decode_access_token_returns_payload():
    """decode_access_token decodes a valid JWT and returns the payload."""
    token = AdminService.create_access_token(subject="42", expires_delta=3600)
    payload = AdminService.decode_access_token(token)
    assert payload["sub"] == "42"
    assert "exp" in payload
    assert "iat" in payload


def test_decode_access_token_raises_401_on_expired_token():
    """decode_access_token raises 401 when token is expired."""
    token = AdminService.create_access_token(subject="1", expires_delta=-10)
    with pytest.raises(HTTPException) as exc_info:
        AdminService.decode_access_token(token)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in exc_info.value.detail.lower()


def test_decode_access_token_raises_401_on_invalid_token():
    """decode_access_token raises 401 when token is malformed."""
    with pytest.raises(HTTPException) as exc_info:
        AdminService.decode_access_token("not-a-valid-jwt-token")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_returns_login_response():
    """authenticate returns AdminLoginResponse on valid credentials."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.hashed_password = "$2b$12$dummyhash"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    login_data = AdminLoginRequest(username="admin", password="correct")

    with patch("passlib.context.CryptContext") as mock_ctx_cls:
        mock_ctx = MagicMock()
        mock_ctx.verify.return_value = True
        mock_ctx_cls.return_value = mock_ctx

        result = await service.authenticate(login_data)

    assert isinstance(result, AdminLoginResponse)
    assert result.token_type == "bearer"
    assert result.expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert isinstance(result.access_token, str)


@pytest.mark.asyncio
async def test_authenticate_raises_401_user_not_found():
    """authenticate raises 401 when username does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    login_data = AdminLoginRequest(username="nonexistent", password="pass")

    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate(login_data)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in exc_info.value.detail


@pytest.mark.asyncio
async def test_authenticate_raises_401_wrong_password():
    """authenticate raises 401 when password is incorrect."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.hashed_password = "$2b$12$dummyhash"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    login_data = AdminLoginRequest(username="admin", password="wrong")

    with patch("passlib.context.CryptContext") as mock_ctx_cls:
        mock_ctx = MagicMock()
        mock_ctx.verify.return_value = False
        mock_ctx_cls.return_value = mock_ctx

        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate(login_data)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_returns_user_response():
    """get_current_user returns AdminUserResponse for a valid token."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.is_active = True

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    token = AdminService.create_access_token(subject="1", expires_delta=3600)

    result = await service.get_current_user(token)

    assert isinstance(result, AdminUserResponse)
    assert result.id == 1
    assert result.username == "admin"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_get_current_user_raises_401_missing_subject():
    """get_current_user raises 401 when token has no subject."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = AdminService(mock_session)

    # Create a token with a custom payload missing 'sub'
    import jwt
    payload = {"exp": datetime.now(timezone.utc) + timedelta(hours=1), "iat": datetime.now(timezone.utc)}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_current_user(token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "missing subject" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_raises_404_user_not_found():
    """get_current_user raises 404 when user does not exist in DB."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    token = AdminService.create_access_token(subject="999", expires_delta=3600)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_current_user(token)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_returns_user_response():
    """create_user creates a new admin user and returns AdminUserResponse."""
    mock_session = AsyncMock(spec=AsyncSession)

    # No existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Simulate flush/refresh setting an id
    async def mock_flush():
        pass

    async def mock_refresh(obj):
        obj.id = 5

    mock_session.flush = mock_flush
    mock_session.refresh = mock_refresh

    service = AdminService(mock_session)
    user_data = AdminUserCreate(username="newadmin", password="securepass123")

    with patch("passlib.context.CryptContext") as mock_ctx_cls:
        mock_ctx = MagicMock()
        mock_ctx.hash.return_value = "$2b$12$hashed"
        mock_ctx_cls.return_value = mock_ctx

        result = await service.create_user(user_data)

    assert isinstance(result, AdminUserResponse)
    assert result.username == "newadmin"
    assert result.is_active is True
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_raises_409_duplicate_username():
    """create_user raises 409 when username already exists."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()  # existing user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    user_data = AdminUserCreate(username="existing", password="pass12345678")

    with pytest.raises(HTTPException) as exc_info:
        await service.create_user(user_data)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_user_updates_is_active():
    """update_user updates is_active field and returns AdminUserResponse."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.is_active = True

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    update_data = AdminUserUpdate(is_active=False)

    result = await service.update_user(1, update_data)

    assert mock_user.is_active is False
    assert isinstance(result, AdminUserResponse)
    assert result.is_active is False


@pytest.mark.asyncio
async def test_update_user_updates_password():
    """update_user hashes and updates the password when provided."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.is_active = True
    mock_user.hashed_password = "old_hash"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    update_data = AdminUserUpdate(password="newpassword123")

    with patch("passlib.context.CryptContext") as mock_ctx_cls:
        mock_ctx = MagicMock()
        mock_ctx.hash.return_value = "$2b$12$newhash"
        mock_ctx_cls.return_value = mock_ctx

        result = await service.update_user(1, update_data)

    assert mock_user.hashed_password == "$2b$12$newhash"


@pytest.mark.asyncio
async def test_update_user_raises_404_not_found():
    """update_user raises 404 when user does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)
    update_data = AdminUserUpdate(is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_user(999, update_data)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_user_succeeds():
    """delete_user deletes the user when not the last admin."""
    mock_user = MagicMock()
    mock_user.id = 2

    mock_session = AsyncMock(spec=AsyncSession)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = mock_user
        else:
            mock_result.scalar.return_value = 3  # total admins
        return mock_result

    mock_session.execute = mock_execute

    service = AdminService(mock_session)
    await service.delete_user(2)

    mock_session.delete.assert_called_once_with(mock_user)


@pytest.mark.asyncio
async def test_delete_user_raises_404_not_found():
    """delete_user raises 404 when user does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = AdminService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_user(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_user_raises_400_last_admin():
    """delete_user raises 400 when trying to delete the last admin."""
    mock_user = MagicMock()
    mock_user.id = 1

    mock_session = AsyncMock(spec=AsyncSession)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = mock_user
        else:
            mock_result.scalar.return_value = 1  # only one admin
        return mock_result

    mock_session.execute = mock_execute

    service = AdminService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_user(1)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "last admin" in exc_info.value.detail.lower()
