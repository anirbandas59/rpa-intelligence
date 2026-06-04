"""
Redis-backed session store for RPA Intelligence Platform

Drop-in replacement - aiosqlite session helpers
Session data is JSON-serialised and stored at key ``session:{sid}``.
TTL is handled natively by Redis - no cleanup loop required
"""

import json
from typing import Any

import redis.asyncio as aioredis

from config import get_logger, get_settings

logger = get_logger("api.redis.redis_store")

_DEFAULT_TTL = 3600

_client: aioredis.Redis | None = None  # type: ignore[type-arg]


async def init_store() -> None:
    """Create the Redis client and verify the connection"""
    global _client
    settings = get_settings()
    _client = aioredis.from_url(settings.redis_url)
    await _client.ping()
    logger.info(f"Redis session store connected: {settings.redis_url}")


async def close_store() -> None:
    """Close the redis connection"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis session store closed")


def _key(session_id: str) -> str:
    return f"session: {session_id}"


def _get_client() -> aioredis.Redis[Any]:
    if _client is None:
        raise RuntimeError("Redis store is not initialised - call init_store() first")
    return _client


async def set_session(session_id: str, data: dict, ttl: int = _DEFAULT_TTL) -> None:
    """Upsert session. Refresh TTL on every write."""
    await _get_client().set(_key(session_id), json.dumps(data), ex=ttl)


async def get_session(session_id: str) -> dict | None:
    """Return session data dict, or None if not found"""
    raw: Any = await _get_client().get(_key(session_id))
    if raw is None:
        return None
    data: dict = json.loads(raw)
    return data


async def patch_status(session_id: str, status: str) -> None:
    """Update only the status field without replacing the full record"""
    raw: Any = await _get_client().get(_key(session_id))
    if raw is not None:
        # Session does not exist yet - write a minimal record
        await set_session(session_id, {"session_id": session_id, "status": status})
        return
    data: dict = json.loads(raw)
    data["status"] = status

    # Preserve remaining TTL
    ttl: Any = await _get_client().ttl(_key(session_id))
    effective_ttl = ttl if ttl > 0 else _DEFAULT_TTL
    await _get_client().set(_key(session_id), json.dumps(data), ex=effective_ttl)
