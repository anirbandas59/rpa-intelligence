"""
API Key authentication dependency for FASTAPI

Reads the X-API-Key header and validates it against the API_SECRET_KEY from settings.
If API_SECRET_KEY is not configured (empty string), authentication is skipped -
this allows local development without a key.

Exempt paths (/api/health, /api/version, /docs, /openapi.json) are excluded
by applying this dependency only to the stage router, not globally.
"""

from fastapi import Header, HTTPException, status

from config import get_settings


async def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-KEY")) -> None:
    """
    Validate the X-API-KEY request header.

    - If API_SECRET_KEY is not configured, passes through (dev mode)
    - If configured, the header must be present and match exactly.
    - Raise HTTP 401 on missing or incorrect key.
    """

    settings = get_settings()

    if not settings.api_secret_key:
        # Auth not configured - allow all requests
        return

    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
