"""
Tests for app.api.routes.admin — Admin authentication and management API routes.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import router as admin_router
from app.schemas import (
    AdminLoginResponse,
    AdminUserResponse,
)


@pytest.fixture
def app():
    """Create a FastAPI app with the admin router."""
    app = FastAPI()
    app.include_router(admin_router)
    return app


@pytest.fixture
def client(app):
    """Create a TestClient for the admin router."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# admin_login
# ---------------------------------------------------------------------------

def test_admin_login_returns_200(client):
    """POST /admin/login returns 200 with JWT token."""
    mock_response = AdminLoginResponse(
        access_token="fake-jwt-token",
        token_type="bearer",
        expires_in=604800,
    )

    mock_service = MagicMock()
    mock_service.authenticate = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        response = client.post(
            "/admin/login",
            json={"username": "admin", "password": "password123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "fake-jwt-token"
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 604800


def test_admin_login_returns_401_invalid_credentials(client):
    """POST /admin/login returns 401 when credentials are invalid."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.authenticate = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    )

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        response = client.post(
            "/admin/login",
            json={"username": "admin", "password": "wrong"},
        )

    assert response.status_code == 401


def test_admin_login_validation_error(client):
    """POST /admin/login returns 422 when required fields are missing."""
    response = client.post("/admin/login", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# get_current_admin
# ---------------------------------------------------------------------------

def test_get_current_admin_returns_200(client):
    """GET /admin/me returns 200 with current admin user info."""
    now = datetime.now(timezone.utc).isoformat()

    mock_admin = {
        "id": 1,
        "username": "admin",
        "email": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    with patch("app.api.routes.admin.verify_admin_token", return_value=mock_admin):
        response = client.get("/admin/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["username"] == "admin"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# create_admin_user
# ---------------------------------------------------------------------------

def test_create_admin_user_returns_201(client):
    """POST /admin/users returns 201 with created user."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = AdminUserResponse(
        id=2,
        username="newadmin",
        email=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    mock_service = MagicMock()
    mock_service.create_user = AsyncMock(return_value=mock_response)

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.post(
                "/admin/users",
                json={"username": "newadmin", "password": "securepass123"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newadmin"
    assert data["is_active"] is True


def test_create_admin_user_returns_409_duplicate(client):
    """POST /admin/users returns 409 when username already exists."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.create_user = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username 'existing' already exists",
        )
    )

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.post(
                "/admin/users",
                json={"username": "existing", "password": "securepass123"},
            )

    assert response.status_code == 409


def test_create_admin_user_validation_error(client):
    """POST /admin/users returns 422 when password is too short."""
    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
        response = client.post(
            "/admin/users",
            json={"username": "ab", "password": "short"},
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# update_admin_user
# ---------------------------------------------------------------------------

def test_update_admin_user_returns_200(client):
    """PUT /admin/users/{id} returns 200 with updated user."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = AdminUserResponse(
        id=2,
        username="updated",
        email=None,
        is_active=False,
        created_at=now,
        updated_at=now,
    )

    mock_service = MagicMock()
    mock_service.update_user = AsyncMock(return_value=mock_response)

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.put(
                "/admin/users/2",
                json={"is_active": False},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


def test_update_admin_user_returns_404(client):
    """PUT /admin/users/{id} returns 404 when user not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.update_user = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found",
        )
    )

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.put(
                "/admin/users/999",
                json={"is_active": True},
            )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# delete_admin_user
# ---------------------------------------------------------------------------

def test_delete_admin_user_returns_204(client):
    """DELETE /admin/users/{id} returns 204 on success."""
    mock_service = MagicMock()
    mock_service.delete_user = AsyncMock(return_value=None)

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.delete("/admin/users/2")

    assert response.status_code == 204


def test_delete_admin_user_returns_404(client):
    """DELETE /admin/users/{id} returns 404 when user not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.delete_user = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found",
        )
    )

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.delete("/admin/users/999")

    assert response.status_code == 404


def test_delete_admin_user_returns_400_last_admin(client):
    """DELETE /admin/users/{id} returns 400 when deleting the last admin."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.delete_user = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last admin user",
        )
    )

    mock_admin = {"id": 1, "username": "admin", "is_active": True}

    with patch("app.api.routes.admin.AdminService", return_value=mock_service):
        with patch("app.api.routes.admin.require_active_admin", return_value=mock_admin):
            response = client.delete("/admin/users/1")

    assert response.status_code == 400
