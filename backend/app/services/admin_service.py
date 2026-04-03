"""
Admin authentication and user management service.

Provides business logic for admin user authentication, JWT token
generation/validation, and user CRUD operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminUserResponse,
    AdminUserCreate,
    AdminUserUpdate,
)

# Module-level password hashing context (avoid recreating on every call)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminService:
    """
    Service layer for admin authentication and user management.

    Handles password hashing, JWT token generation/validation,
    and admin user CRUD operations.

    Args:
        session: Async SQLAlchemy session for the App database.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the AdminService with a database session.

        Args:
            session: Async SQLAlchemy session for the App database.
        """
        self.session = session

    async def authenticate(self, login_data: AdminLoginRequest) -> AdminLoginResponse:
        """
        Authenticate an admin user and return a JWT token.

        Verifies the provided username and password against the database,
        then generates and returns a JWT access token.

        Args:
            login_data: Login request with username and password.

        Returns:
            AdminLoginResponse: JWT access token and token type.

        Raises:
            HTTPException: 401 Unauthorized if credentials are invalid.
        """
        from app.models.admin import AdminUser
        from sqlalchemy import select

        # Query admin user by username
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.username == login_data.username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify password hash against stored hash
        if not pwd_context.verify(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate JWT token with user ID and expiration
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        access_token = self.create_access_token(
            subject=str(user.id),
            expires_delta=expires_in,
        )

        return AdminLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def get_current_user(self, token: str) -> AdminUserResponse:
        """
        Get the current authenticated admin user from a JWT token.

        Decodes the JWT token, extracts the user ID, and fetches
        the corresponding admin user from the database.

        Args:
            token: JWT access token string.

        Returns:
            AdminUserResponse: Admin user details (excluding sensitive information).

        Raises:
            HTTPException: 401 Unauthorized if token is invalid or expired.
            HTTPException: 404 Not Found if user does not exist.
        """
        # Decode JWT token and extract user ID
        payload = self.decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Query admin user by ID
        from app.models.admin import AdminUser
        from sqlalchemy import select

        result = await self.session.execute(
            select(AdminUser).where(AdminUser.id == int(user_id))
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return AdminUserResponse(
            id=user.id,
            username=user.username,
            email=None,
            is_active=user.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def create_user(self, user_data: AdminUserCreate) -> AdminUserResponse:
        """
        Create a new admin user.

        Hashes the password and creates a new admin user record.

        Args:
            user_data: New admin user data (username, password, email).

        Returns:
            AdminUserResponse: Created admin user information.

        Raises:
            HTTPException: 409 Conflict if username already exists.
        """
        from app.models.admin import AdminUser
        from sqlalchemy import select

        # Check if username already exists
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.username == user_data.username)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{user_data.username}' already exists",
            )

        # Hash the password
        hashed_password = pwd_context.hash(user_data.password)

        # Create AdminUser ORM model
        new_user = AdminUser(
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=True,
        )
        self.session.add(new_user)
        await self.session.flush()
        await self.session.refresh(new_user)

        return AdminUserResponse(
            id=new_user.id,
            username=new_user.username,
            email=None,
            is_active=new_user.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def update_user(
        self, user_id: int, update_data: AdminUserUpdate
    ) -> AdminUserResponse:
        """
        Update an existing admin user.

        Only non-None fields in update_data are applied. If password
        is provided, it is hashed before storage.

        Args:
            user_id: ID of admin user to update.
            update_data: Fields to update (password, email, is_active).

        Returns:
            AdminUserResponse: Updated admin user information.

        Raises:
            HTTPException: 404 Not Found if user does not exist.
        """
        from app.models.admin import AdminUser
        from sqlalchemy import select

        # Fetch admin user by ID
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin user not found",
            )

        # Hash password if provided in update_data
        if update_data.password is not None:
            user.hashed_password = pwd_context.hash(update_data.password)

        # Apply non-None fields to the model
        if update_data.email is not None:
            pass  # email field not in model yet, skip

        if update_data.is_active is not None:
            user.is_active = update_data.is_active

        await self.session.flush()
        await self.session.refresh(user)

        return AdminUserResponse(
            id=user.id,
            username=user.username,
            email=None,
            is_active=user.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def delete_user(self, user_id: int) -> None:
        """
        Delete an admin user.

        Args:
            user_id: ID of admin user to delete.

        Raises:
            HTTPException: 404 Not Found if user does not exist.
            HTTPException: 400 Bad Request if trying to delete the last admin user.
        """
        from app.models.admin import AdminUser
        from sqlalchemy import select, func

        # Fetch admin user by ID
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin user not found",
            )

        # Check if this is the last admin user
        count_result = await self.session.execute(select(func.count(AdminUser.id)))
        total_admins = count_result.scalar()
        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin user",
            )

        # Delete the user
        await self.session.delete(user)
        await self.session.flush()

    @staticmethod
    def create_access_token(
        subject: str, expires_delta: Optional[int] = None
    ) -> str:
        """
        Create a JWT access token for the given subject.

        Args:
            subject: The token subject (typically user ID or username).
            expires_delta: Token lifetime in seconds. Uses default if None.

        Returns:
            str: Encoded JWT token string.
        """
        import jwt

        now = datetime.now(timezone.utc)

        if expires_delta is not None:
            expire = now + timedelta(seconds=expires_delta)
        else:
            expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
        }

        encoded_token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return encoded_token

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """
        Decode and validate a JWT access token.

        Args:
            token: Encoded JWT token string.

        Returns:
            dict: Decoded token payload.

        Raises:
            HTTPException: 401 Unauthorized if token is invalid or expired.
        """
        import jwt
        from jwt import PyJWTError

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (PyJWTError, jwt.InvalidTokenError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
