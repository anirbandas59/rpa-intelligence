"""
Episodic memory for agent learning from past stage outcomes.

Provides EpisodicMemory class for storing and retrieving past assessment results
using keyword-based similarity matching. Enables few-shot learning without requiring
vector databases - uses simple SQL ILIKE queries on keyword tags.

Key features:
- Store stage outcomes with keyword tags in AgentMemory table
- Retrieve similar past cases via keyword matching (SQL ILIKE)
- No vector embeddings required (lightweight, no external dependencies)
- Used by AssessmentService for few-shot learning context

Storage:
- Table: AgentMemory (use_case_id, stage, memory_type, content JSONB, keywords TEXT)
- Keywords: Space-separated string for ILIKE matching (e.g., "invoice automation sap")
- Content: Arbitrary JSON dict with stage-specific data

Retrieval:
- Query keywords matched via SQL ILIKE (case-insensitive substring match)
- Optionally filtered by stage (s1, s2, s3, s4)
- Returns most recent matches (ORDER BY created_at DESC)

Usage:
    memory = EpisodicMemory(db)
    await memory.store(use_case_id, project_id, "s1", "assessment", result_dict, ["invoice", "automation"])
    similar = await memory.retrieve_similar(["invoice", "sap"], stage="s1", limit=3)
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory, new_uuid

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """
    Stores and retrieves agent episodic memories from the database.

    Memory is stored as AgentMemory records with keyword tags.
    Retrieval uses SQL ILIKE matching on keywords column.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        use_case_id: str,
        project_id: str,
        stage: str,
        memory_type: str,
        content: dict,
        keywords: list[str],
    ) -> AgentMemory:
        """
        Store new episodic memory record for future retrieval.

        Creates AgentMemory record with keyword tags for similarity matching.
        Keywords are joined with spaces for SQL ILIKE queries.

        Args:
            use_case_id: UseCase ID this memory relates to
            project_id: Project ID for organizational grouping
            stage: Stage identifier (s1, s2, s3, s4)
            memory_type: Memory type tag (e.g., "assessment", "complexity", "timeline")
            content: Arbitrary JSON dict with stage-specific data
            keywords: List of keywords for similarity matching (e.g., ["invoice", "automation", "sap"])

        Returns:
            Created AgentMemory record with generated ID
        """
        memory = AgentMemory(
            id=new_uuid(),
            use_case_id=use_case_id,
            project_id=project_id,
            stage=stage,
            memory_type=memory_type,
            content=content,
            keywords=" ".join(keywords),
            created_at=datetime.now(UTC),
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        logger.info(f"[memory] Stored {memory_type} memory for use_case={use_case_id} stage={stage}")
        return memory

    async def retrieve_similar(
        self,
        query_keywords: list[str],
        stage: str | None = None,
        limit: int = 3,
    ) -> list[AgentMemory]:
        """
        Retrieve memories matching any of the query keywords via SQL ILIKE.

        Builds SQL query with OR conditions for keyword matching (case-insensitive
        substring match). Optionally filters by stage and returns most recent matches.

        Args:
            query_keywords: List of keywords to match (uses first 5 keywords max)
            stage: Optional stage filter (s1, s2, s3, s4) - None matches all stages
            limit: Maximum number of memories to return (default: 3)

        Returns:
            List of AgentMemory records ordered by created_at DESC (most recent first)

        Query pattern:
            WHERE (keywords ILIKE '%kw1%' OR keywords ILIKE '%kw2%' OR ...)
            AND stage = 's1'
            ORDER BY created_at DESC
            LIMIT 3
        """
        if not query_keywords:
            return []

        conditions = [AgentMemory.keywords.ilike(f"%{kw}%") for kw in query_keywords[:5]]
        query = select(AgentMemory).where(or_(*conditions))

        if stage:
            query = query.where(AgentMemory.stage == stage)

        query = query.order_by(AgentMemory.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        memories = result.scalars().all()

        logger.info(f"[memory] Retrieved {len(memories)} memories for keywords={query_keywords[:3]} stage={stage}")
        return list(memories)

    async def retrieve_for_use_case(self, use_case_id: str) -> list[AgentMemory]:
        """Get all memories for a specific use-case, most recent first."""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.use_case_id == use_case_id).order_by(AgentMemory.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, memory_id: str) -> bool:
        """Delete a specific memory by ID. Returns True if found and deleted."""
        result = await self.db.execute(select(AgentMemory).where(AgentMemory.id == memory_id))
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        self.db.delete(memory)
        await self.db.commit()
        return True
