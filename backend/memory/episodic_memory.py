"""
Episodic memory for agents — stores and retrieves past stage outcomes.
Uses keyword-based SQL similarity (no vector DB required).
"""
import logging
from datetime import datetime

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
        """Store a new memory record."""
        memory = AgentMemory(
            id=new_uuid(),
            use_case_id=use_case_id,
            project_id=project_id,
            stage=stage,
            memory_type=memory_type,
            content=content,
            keywords=" ".join(keywords),
            created_at=datetime.utcnow(),
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
        Retrieve memories matching any of the query keywords.
        Optionally filter by stage. Returns up to `limit` most recent results.
        """
        if not query_keywords:
            return []

        conditions = [
            AgentMemory.keywords.ilike(f"%{kw}%")
            for kw in query_keywords[:5]
        ]
        query = select(AgentMemory).where(or_(*conditions))

        if stage:
            query = query.where(AgentMemory.stage == stage)

        query = query.order_by(AgentMemory.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        memories = result.scalars().all()

        logger.info(
            f"[memory] Retrieved {len(memories)} memories for keywords={query_keywords[:3]} stage={stage}"
        )
        return list(memories)

    async def retrieve_for_use_case(self, use_case_id: str) -> list[AgentMemory]:
        """Get all memories for a specific use-case, most recent first."""
        result = await self.db.execute(
            select(AgentMemory)
            .where(AgentMemory.use_case_id == use_case_id)
            .order_by(AgentMemory.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, memory_id: str) -> bool:
        """Delete a specific memory by ID. Returns True if found and deleted."""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.id == memory_id)
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        self.db.delete(memory)
        await self.db.commit()
        return True
