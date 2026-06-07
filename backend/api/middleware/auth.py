"""
API Key authentication middleware for FastAPI routes.

Provides header-based API key authentication as an alternative to JWT tokens.
Validates X-API-KEY header against API_SECRET_KEY from environment configuration.
Supports development mode bypass when API_SECRET_KEY is not configured.

Usage:
- Apply via Depends(verify_api_key) on protected routes
- Public endpoints (health, docs) bypass by not using dependency
- Applied selectively to stage routers, not globally

Authentication modes:
- Production: X-API-KEY header must match API_SECRET_KEY
- Development: Auth bypass if API_SECRET_KEY not set (empty string)
"""

from fastapi import Header, HTTPException, status

from config import get_settings


async def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-KEY")) -> None:
    """
    Validate X-API-KEY request header against configured API secret.

    Provides simple header-based authentication for API access. Bypasses
    validation in development mode when API_SECRET_KEY is not configured.

    Args:
        x_api_key: API key from X-API-KEY header (optional, injected by FastAPI)

    Raises:
        HTTPException: 401 if API key is missing or doesn't match configured secret

    Behavior:
    - No API_SECRET_KEY set: Allow all requests (development mode)
    - API_SECRET_KEY set: Require exact match with header value
    """
    settings = get_settings()

    # Development mode: skip auth if API_SECRET_KEY not configured
    if not settings.api_secret_key:
        return

    # Production mode: validate API key matches configuration
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
