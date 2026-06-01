"""Memory API — view and manage agent episodic memories."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from db.models import User
from memory.episodic_memory import EpisodicMemory

router = APIRouter()
logger = logging.getLogger(__name__)


class MemoryResponse(BaseModel):
    id: str
    use_case_id: str
    project_id: str
    memory_type: str
    stage: str
    content: dict
    keywords: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/{id}/memories", response_model=list[MemoryResponse])
async def list_use_case_memories(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all episodic memories for a use-case."""
    mem = EpisodicMemory(db)
    memories = await mem.retrieve_for_use_case(id)
    return memories


@router.delete("/{id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    id: str,
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific episodic memory."""
    mem = EpisodicMemory(db)
    deleted = await mem.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
