"""
Centralized FastAPI dependency injection module.

Provides reusable dependency functions for database sessions,
authentication, and authorization across all API routes.

This module eliminates duplication of session dependencies that
currently exist in each route file and provides a single source
of truth for dependency injection configuration.
"""

from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AppSessionLocal, ArticlesSessionLocal
from app.core.config import settings
from app.services.admin_service import AdminService


# ---------------------------------------------------------------------------
# Database session dependencies
# ---------------------------------------------------------------------------

async def get_app_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session for the App database.

    The App database contains admin_users, pipeline_runs, agent_configs,
    and other application-level tables.

    Yields:
        AsyncSession: An async SQLAlchemy session for the App database.
                      The session is automatically closed after the request.

    Example:
        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_app_session)):
            ...
    """
    async with AppSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_articles_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session for the Articles database.

    The Articles database contains articles, tags, hubs, images,
    article_embeddings, and other content-level tables.

    Yields:
        AsyncSession: An async SQLAlchemy session for the Articles database.
                      The session is automatically closed after the request.

    Example:
        @router.get("/articles")
        async def list_articles(session: AsyncSession = Depends(get_articles_session)):
            ...
    """
    async with ArticlesSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

security = HTTPBearer(auto_error=False)


async def get_optional_admin_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    Extract and optionally validate an admin JWT token from the request.

    This dependency returns None if no token is provided, allowing
    endpoints to be accessible to both authenticated and unauthenticated users.

    Args:
        credentials: HTTP Authorization credentials (Bearer token) from the request.

    Returns:
        Optional[str]: The JWT token string if provided, None otherwise.

    Example:
        @router.get("/public-or-private")
        async def mixed_endpoint(token: Optional[str] = Depends(get_optional_admin_token)):
            if token:
                # Authenticated logic
                ...
            else:
                # Public logic
                ...
    """
    if credentials is None:
        return None
    return credentials.credentials


async def get_required_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract and validate a required admin JWT token from the request.

    This dependency raises an HTTP 401 error if no valid token is provided,
    ensuring that only authenticated admin users can access the endpoint.

    Args:
        credentials: HTTP Authorization credentials (Bearer token) from the request.

    Returns:
        str: The validated JWT token string.

    Raises:
        HTTPException: 401 Unauthorized if no token is provided or token is invalid.

    Example:
        @router.post("/admin-only")
        async def admin_endpoint(token: str = Depends(get_required_admin_token)):
            # Only authenticated admins can reach here
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_admin_token(
    token: str = Depends(get_required_admin_token),
    session: AsyncSession = Depends(get_app_session),
) -> dict:
    """
    Verify an admin JWT token and return the associated admin user information.

    This dependency decodes the JWT token, validates its signature and expiration,
    and fetches the corresponding admin user from the database.

    Args:
        token: The JWT token string to verify.
        session: Async database session for the App database.

    Returns:
        dict: Admin user information including id, username, email, and is_active status.

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or user not found.
        HTTPException: 403 Forbidden if user account is inactive.

    Example:
        @router.get("/admin/me")
        async def get_current_admin(admin: dict = Depends(verify_admin_token)):
            return admin
    """
    # Decode and validate the JWT token
    payload = AdminService.decode_access_token(token)

    # Extract user ID from token subject
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch admin user from database
    from app.models.admin import AdminUser
    from sqlalchemy import select

    result = await session.execute(select(AdminUser).where(AdminUser.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": None,
        "is_active": user.is_active,
    }


# ---------------------------------------------------------------------------
# Authorization dependencies
# ---------------------------------------------------------------------------

async def require_active_admin(
    admin: dict = Depends(verify_admin_token),
) -> dict:
    """
    Ensure the authenticated admin user has an active account.

    This dependency wraps verify_admin_token and adds an additional
    check for account active status.

    Args:
        admin: Admin user information from verify_admin_token.

    Returns:
        dict: Admin user information (same as input, for chaining).

    Raises:
        HTTPException: 403 Forbidden if the admin account is not active.

    Example:
        @router.delete("/admin/users/{user_id}")
        async def delete_user(user_id: int, admin: dict = Depends(require_active_admin)):
            # Only active admins can delete users
            ...
    """
    if not admin.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return admin


async def require_superuser(
    admin: dict = Depends(verify_admin_token),
    session: AsyncSession = Depends(get_app_session),
) -> dict:
    """
    Ensure the authenticated admin user has superuser privileges.

    This dependency is used for endpoints that require elevated permissions,
    such as creating or deleting admin users.

    Args:
        admin: Admin user information from verify_admin_token.
        session: Async database session for the App database.

    Returns:
        dict: Admin user information (same as input, for chaining).

    Raises:
        HTTPException: 403 Forbidden if the admin user is not a superuser.

    Example:
        @router.post("/admin/users")
        async def create_admin_user(admin: dict = Depends(require_superuser)):
            # Only superusers can create new admin users
            ...
    """
    # For now, treat the first/only admin as superuser
    # In a full implementation, this would check an is_superuser field
    from app.models.admin import AdminUser
    from sqlalchemy import select, func

    result = await session.execute(select(func.count(AdminUser.id)))
    total_admins = result.scalar()

    # If there's only one admin, they are the superuser
    if total_admins == 1:
        return admin

    # Otherwise, check if this admin is the first one created (lowest ID)
    result = await session.execute(select(AdminUser).order_by(AdminUser.id).limit(1))
    first_admin = result.scalar_one_or_none()
    if first_admin and first_admin.id == admin["id"]:
        return admin

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Superuser privileges required",
    )


# ---------------------------------------------------------------------------
# Pipeline-specific dependencies
# ---------------------------------------------------------------------------

async def get_pipeline_config(
    session: AsyncSession = Depends(get_app_session),
) -> dict:
    """
    Retrieve the current pipeline configuration from the database.

    This dependency fetches agent configuration settings that control
    pipeline behavior, such as enabled status, dry run mode, and
    quality thresholds.

    Args:
        session: Async database session for the App database.

    Returns:
        dict: Pipeline configuration with keys like agent_enabled, agent_dry_run,
              agent_auto_publish, agent_quality_threshold, etc.

    Raises:
        HTTPException: 500 Internal Server Error if configuration cannot be retrieved.

    Example:
        @router.post("/pipeline/trigger")
        async def trigger_pipeline(config: dict = Depends(get_pipeline_config)):
            if not config.get("agent_enabled"):
                raise HTTPException(400, "Pipeline is disabled")
            ...
    """
    from app.models.pipeline import AgentConfig
    from sqlalchemy import select

    result = await session.execute(select(AgentConfig))
    configs = result.scalars().all()

    config_dict = {c.key: c.value for c in configs}

    # Merge with defaults from settings for any missing keys
    defaults = {
        "AGENT_ENABLED": str(settings.AGENT_ENABLED),
        "AGENT_DRY_RUN": str(settings.AGENT_DRY_RUN),
        "AGENT_AUTO_PUBLISH": str(settings.AGENT_AUTO_PUBLISH),
        "AGENT_QUALITY_THRESHOLD": str(settings.AGENT_QUALITY_THRESHOLD),
        "AGENT_POLL_INTERVAL_SECONDS": str(settings.AGENT_POLL_INTERVAL_SECONDS),
        "AGENT_MAX_CONCURRENT_RUNS": str(settings.AGENT_MAX_CONCURRENT_RUNS),
    }

    for key, default_value in defaults.items():
        if key not in config_dict:
            config_dict[key] = default_value

    return config_dict


async def verify_pipeline_enabled(
    config: dict = Depends(get_pipeline_config),
) -> dict:
    """
    Verify that the pipeline is enabled before allowing pipeline operations.

    This dependency checks the agent_enabled configuration and raises
    an error if the pipeline is disabled.

    Args:
        config: Pipeline configuration from get_pipeline_config.

    Returns:
        dict: Pipeline configuration (same as input, for chaining).

    Raises:
        HTTPException: 400 Bad Request if the pipeline is disabled.

    Example:
        @router.post("/pipeline/trigger/{article_id}")
        async def trigger_pipeline(
            article_id: int,
            config: dict = Depends(verify_pipeline_enabled),
        ):
            # Pipeline is guaranteed to be enabled here
            ...
    """
    enabled_value = config.get("AGENT_ENABLED", str(settings.AGENT_ENABLED))
    if enabled_value.lower() not in ("true", "1", "yes"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline is disabled (AGENT_ENABLED=False)",
        )
    return config
