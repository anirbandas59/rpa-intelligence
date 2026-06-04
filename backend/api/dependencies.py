from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth import decode_token
from config.settings import get_settings
from db.models import User
from db.session import get_session_factory

security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth


async def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Injectable factory so background tasks can be overridden in tests."""
    return get_session_factory()


async def get_db() -> AsyncSession:
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
        # Return or create a default dev user
        result = await db.execute(
            select(User).where(User.email == "dev@localhost")
        )
        dev_user = result.scalar_one_or_none()

        if not dev_user:
            # Create default dev user
            from auth import hash_password
            dev_user = User(
                email="dev@localhost",
                hashed_password=hash_password("dev"),
                role="superuser",  # Give superuser role for full access in dev
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

    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
    if user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")
    return user
