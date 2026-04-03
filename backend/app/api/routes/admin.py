"""
Admin authentication and management API routes.

Provides endpoints for admin user authentication, session management,
and user administration.

All endpoints use the AdminService for business logic and the
centralized database session dependency from app.dependencies.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_app_session, verify_admin_token, require_active_admin
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminUserResponse,
    AdminUserCreate,
    AdminUserUpdate,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="Authenticate admin user",
)
async def admin_login(
    login_data: AdminLoginRequest,
    session: AsyncSession = Depends(get_app_session),
) -> AdminLoginResponse:
    """
    Authenticate admin user and return JWT token.

    Args:
        login_data: Login request with username and password.
        session: Async database session.

    Returns:
        AdminLoginResponse: JWT access token and token type.

    Raises:
        HTTPException: 401 Unauthorized if credentials are invalid.
    """
    service = AdminService(session)
    return await service.authenticate(login_data)


@router.get(
    "/me",
    response_model=AdminUserResponse,
    summary="Get current admin user",
)
async def get_current_admin(
    admin_user: dict = Depends(verify_admin_token),
) -> AdminUserResponse:
    """
    Get current authenticated admin user information.

    Args:
        admin_user: Verified admin user from token.

    Returns:
        AdminUserResponse: Admin user details (excluding sensitive information).
    """
    return AdminUserResponse(
        id=admin_user["id"],
        username=admin_user["username"],
        email=admin_user.get("email"),
        is_active=admin_user["is_active"],
        created_at=admin_user.get("created_at", None),
        updated_at=admin_user.get("updated_at", None),
    )


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new admin user",
)
async def create_admin_user(
    user_data: AdminUserCreate,
    admin_user: dict = Depends(require_active_admin),
    session: AsyncSession = Depends(get_app_session),
) -> AdminUserResponse:
    """
    Create a new admin user.

    Args:
        user_data: New admin user data (username, password, email).
        admin_user: Current authenticated admin (for authorization).
        session: Async database session.

    Returns:
        AdminUserResponse: Created admin user information.

    Raises:
        HTTPException: 409 Conflict if username already exists.
    """
    service = AdminService(session)
    return await service.create_user(user_data)


@router.put(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Update an admin user",
)
async def update_admin_user(
    user_id: int,
    update_data: AdminUserUpdate,
    admin_user: dict = Depends(require_active_admin),
    session: AsyncSession = Depends(get_app_session),
) -> AdminUserResponse:
    """
    Update an existing admin user.

    Args:
        user_id: ID of admin user to update.
        update_data: Fields to update (password, email, is_active).
        admin_user: Current authenticated admin (for authorization).
        session: Async database session.

    Returns:
        AdminUserResponse: Updated admin user information.

    Raises:
        HTTPException: 404 Not Found if user does not exist.
    """
    service = AdminService(session)
    return await service.update_user(user_id, update_data)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an admin user",
)
async def delete_admin_user(
    user_id: int,
    admin_user: dict = Depends(require_active_admin),
    session: AsyncSession = Depends(get_app_session),
) -> None:
    """
    Delete an admin user.

    Args:
        user_id: ID of admin user to delete.
        admin_user: Current authenticated admin (for authorization).
        session: Async database session.

    Raises:
        HTTPException: 404 Not Found if user does not exist.
        HTTPException: 400 Bad Request if trying to delete the last admin user.
    """
    service = AdminService(session)
    await service.delete_user(user_id)
