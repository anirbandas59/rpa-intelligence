from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import UseCase, User
from api.dependencies import get_db, get_current_user

router = APIRouter()


class UseCaseCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None


class UseCaseResponse(BaseModel):
    id: str
    name: str
    description: str | None


@router.post("", response_model=UseCaseResponse)
async def create_use_case(
    req: UseCaseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    use_case = UseCase(project_id=req.project_id, name=req.name, description=req.description)
    db.add(use_case)
    await db.commit()
    await db.refresh(use_case)
    return use_case


@router.get("/{id}", response_model=UseCaseResponse)
async def get_use_case(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Use case not found")
    return use_case
