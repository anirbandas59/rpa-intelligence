"""
FastAPI dependency injection functions for authentication and database access.

Provides injectable dependencies for route handlers using FastAPI's Depends
pattern. Handles database session management, JWT authentication, and role-based
access control. Supports development mode bypass for easier local testing.

Key dependencies:
- get_db: Provides async database session with automatic cleanup
- get_current_user: Extracts and validates JWT token, returns authenticated User
- require_superuser: Enforces superuser role for privileged operations

Authentication modes:
- Production: JWT Bearer token required (SECRET_KEY set)
- Development: Auth bypass with auto-created dev@localhost superuser (no SECRET_KEY)
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth import decode_token
from config.settings import get_settings
from db.models import User
from db.session import get_session_factory

# HTTPBearer security scheme with auto_error=False to allow optional auth
security = HTTPBearer(auto_error=False)


async def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Get async session factory for creating database sessions.

    Injectable factory that allows overriding in tests. Used by background
    tasks that need to create their own sessions outside request context.

    Returns:
        Async session maker factory
    """
    return get_session_factory()


async def get_db() -> AsyncSession:
    """
    Dependency that provides async database session with automatic cleanup.

    Creates a new database session for each request and automatically closes
    it when the request completes (via yield). Handles transaction rollback
    on errors. Use via FastAPI Depends(get_db).

    Yields:
        Async database session for the request
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.

    In development mode (ENVIRONMENT=development and no SECRET_KEY set),
    authentication is bypassed and a default dev user is created/returned.

    Args:
        credentials: JWT Bearer token from Authorization header
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    settings = get_settings()

    # DEV MODE: Bypass auth if in development and no SECRET_KEY configured
    if settings.environment == "development" and not settings.secret_key:
        # Look up or create default dev user for local development
        result = await db.execute(
            select(User).where(User.email == "dev@localhost")
        )
        dev_user = result.scalar_one_or_none()

        if not dev_user:
            # Auto-create dev user with superuser role for full access
            from auth import hash_password
            dev_user = User(
                email="dev@localhost",
                hashed_password=hash_password("dev"),
                role="superuser",
                is_active=True,
            )
            db.add(dev_user)
            await db.commit()
            await db.refresh(dev_user)

        return dev_user

    # PRODUCTION MODE: Require valid JWT token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract and decode JWT token
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up user from token subject (user ID)
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_superuser(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that enforces superuser role for privileged operations.

    Chains with get_current_user to first authenticate, then verify superuser
    role. Use on routes that manage LLM config, prompt variants, or users.

    Args:
        user: Authenticated user from get_current_user dependency

    Returns:
        User object if superuser

    Raises:
        HTTPException: 403 if user is not a superuser
    """
    if user.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser required"
        )
    return user
