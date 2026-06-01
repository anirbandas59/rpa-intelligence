"""Unit tests for EpisodicMemory class."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from memory.episodic_memory import EpisodicMemory
from db.models import AgentMemory


@pytest.fixture
def mock_db_session():
    """Create a mocked AsyncSession."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_store_creates_memory(mock_db_session):
    """Test that store() creates and commits a memory record."""
    mem = EpisodicMemory(mock_db_session)

    # Mock the refresh call
    async def mock_refresh(obj):
        obj.id = "test-memory-id"

    mock_db_session.refresh = mock_refresh

    result = await mem.store(
        use_case_id="uc-123",
        project_id="proj-456",
        stage="s1",
        memory_type="assessment_result",
        content={"score": 75, "decision": "QUICK_WIN"},
        keywords=["test", "assessment"],
    )

    # Verify that db.add was called
    assert mock_db_session.add.called
    # Verify that db.commit was called
    assert mock_db_session.commit.called
    # Verify result is AgentMemory instance
    assert isinstance(result, AgentMemory)
    assert result.memory_type == "assessment_result"
    assert result.stage == "s1"


@pytest.mark.asyncio
async def test_retrieve_similar_empty_keywords(mock_db_session):
    """Test that retrieve_similar returns empty list for empty keywords."""
    mem = EpisodicMemory(mock_db_session)

    result = await mem.retrieve_similar([], stage="s1")

    assert result == []
    # Should not execute query if keywords empty
    assert not mock_db_session.execute.called


@pytest.mark.asyncio
async def test_retrieve_similar_with_results(mock_db_session):
    """Test that retrieve_similar executes query and returns results."""
    mem = EpisodicMemory(mock_db_session)

    # Create mock memory objects
    mock_memory1 = MagicMock(spec=AgentMemory)
    mock_memory1.id = "mem-1"
    mock_memory1.keywords = "test assessment"

    mock_memory2 = MagicMock(spec=AgentMemory)
    mock_memory2.id = "mem-2"
    mock_memory2.keywords = "test scoring"

    # Mock the query execution - scalars().all() should return list
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_memory1, mock_memory2]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db_session.execute = AsyncMock(return_value=mock_result)

    result = await mem.retrieve_similar(
        query_keywords=["test", "assessment"],
        stage="s1",
        limit=5
    )

    assert len(result) == 2
    assert result[0].id == "mem-1"
    assert result[1].id == "mem-2"
    assert mock_db_session.execute.called


@pytest.mark.asyncio
async def test_delete_existing_memory(mock_db_session):
    """Test that delete returns True for existing memory."""
    mem = EpisodicMemory(mock_db_session)

    # Mock memory found
    mock_memory = MagicMock(spec=AgentMemory)
    mock_memory.id = "mem-to-delete"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory

    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.delete = MagicMock()  # Not async
    mock_db_session.commit = AsyncMock()

    deleted = await mem.delete("mem-to-delete")

    assert deleted is True
    assert mock_db_session.delete.called
    assert mock_db_session.commit.called


@pytest.mark.asyncio
async def test_delete_nonexistent_memory(mock_db_session):
    """Test that delete returns False for non-existent memory."""
    mem = EpisodicMemory(mock_db_session)

    # Mock memory not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = AsyncMock()

    deleted = await mem.delete("nonexistent-id")

    assert deleted is False
    # Should not attempt to delete or commit
    assert not mock_db_session.delete.called
    assert not mock_db_session.commit.called


@pytest.mark.asyncio
async def test_retrieve_for_use_case(mock_db_session):
    """Test retrieving all memories for a specific use-case."""
    mem = EpisodicMemory(mock_db_session)

    # Create mock memories
    mock_memory1 = MagicMock(spec=AgentMemory)
    mock_memory1.id = "mem-1"

    mock_memory2 = MagicMock(spec=AgentMemory)
    mock_memory2.id = "mem-2"

    # Mock the query execution - scalars().all() should return list
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_memory1, mock_memory2]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db_session.execute = AsyncMock(return_value=mock_result)

    result = await mem.retrieve_for_use_case("uc-123")

    assert len(result) == 2
    assert result[0].id == "mem-1"
    assert result[1].id == "mem-2"
    assert mock_db_session.execute.called
