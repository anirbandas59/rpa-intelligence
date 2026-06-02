from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass

_engine: AsyncEngine | None = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            echo=False,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
        )
    return _engine

def get_session_factory(engine: AsyncEngine | None = None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
