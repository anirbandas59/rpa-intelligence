"""
Shared pytest fixtures for all tests.
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from api.main import app
from db.session import Base
from db.models import User, Project
from auth import create_access_token


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine():
    """Create in-memory test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create test database session."""
    session_factory = async_sessionmaker(test_db_engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        yield session


@pytest.fixture
async def test_user(test_db_session):
    """Create test user."""
    user = User(
        email="test@example.com",
        hashed_password="$2b$12$test_hash_for_testing_only",  # Skip real hashing in tests
        role="user",
        is_active=True,
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)

    return user


@pytest.fixture
async def test_superuser(test_db_session):
    """Create test superuser."""
    user = User(
        email="admin@example.com",
        hashed_password="$2b$12$test_hash_for_testing_only",  # Skip real hashing in tests
        role="superuser",
        is_active=True,
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)

    return user


@pytest.fixture
async def test_user_token(test_user):
    """Generate JWT token for test user."""
    return create_access_token(test_user.id)


@pytest.fixture
async def test_superuser_token(test_superuser):
    """Generate JWT token for test superuser."""
    return create_access_token(test_superuser.id)


@pytest.fixture
async def test_project(test_db_session, test_user):
    """Create test project."""
    project = Project(
        name="Test Project",
        description="A test project for integration tests",
        created_by=test_user.id,
    )
    test_db_session.add(project)
    await test_db_session.commit()
    await test_db_session.refresh(project)

    return {"id": project.id, "name": project.name}


@pytest.fixture
async def async_client(test_db_engine):
    """
    Create async HTTP client with dependency override for database.
    """

    # Override get_db dependency to use test database
    async def override_get_db():
        session_factory = async_sessionmaker(test_db_engine, expire_on_commit=False, class_=AsyncSession)
        async with session_factory() as session:
            yield session

    from api.dependencies import get_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()
