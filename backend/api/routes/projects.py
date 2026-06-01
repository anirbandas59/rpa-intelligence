from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Project, User, WeightConfig, PhaseConfig, UseCase
from api.dependencies import get_db, get_current_user
from core.scoring.weight_matrix import load_weight_matrix
from services.timeline_service import DEFAULT_BUFFERS

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime


class UseCaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    source_platform: str | None
    install_status: str | None
    created_at: datetime


class WeightConfigRequest(BaseModel):
    """Request to update weight config for a project."""

    config: dict[str, dict[str, int]]  # Weight matrix override
    yes_threshold: int = 50


class WeightConfigResponse(BaseModel):
    """Response for weight config."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    is_active: bool
    config: dict
    yes_threshold: int
    created_at: datetime


class PhaseConfigRequest(BaseModel):
    """Request to update phase buffer configuration."""

    config: dict[str, int]  # Buffer overrides: {"define": 2, "design": {"S": 1, "M": 2, ...}, ...}
    sprint_length_weeks: int = 2


class PhaseConfigResponse(BaseModel):
    """Response for phase config."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    is_active: bool
    config: dict
    sprint_length_weeks: int
    created_at: datetime


@router.post("", response_model=ProjectResponse)
async def create_project(
    req: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(name=req.name, description=req.description, created_by=user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project))
    return result.scalars().all()


@router.get("/{id}/use-cases", response_model=list[UseCaseListItem])
async def list_project_use_cases(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all use cases for a project."""
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch use cases
    use_cases_result = await db.execute(
        select(UseCase).where(UseCase.project_id == id).order_by(UseCase.created_at.desc())
    )
    return use_cases_result.scalars().all()


@router.get("/{id}/weights", status_code=status.HTTP_200_OK)
async def get_project_weights(
    id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get active WeightConfig for project.
    If none exists, returns default weight matrix.

    Returns:
        WeightConfig or default weights
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch active weight config
    config_result = await db.execute(select(WeightConfig).where(WeightConfig.project_id == id, WeightConfig.is_active))
    weight_config = config_result.scalars().first()

    if weight_config:
        return {
            "id": weight_config.id,
            "project_id": weight_config.project_id,
            "name": weight_config.name,
            "is_active": weight_config.is_active,
            "config": weight_config.config,
            "yes_threshold": weight_config.yes_threshold,
            "created_at": weight_config.created_at.isoformat(),
            "source": "project_override",
        }
    else:
        # Return default matrix
        default_matrix = load_weight_matrix()
        return {
            "id": None,
            "project_id": id,
            "name": "default",
            "is_active": True,
            "config": default_matrix,
            "yes_threshold": 50,
            "created_at": None,
            "source": "default",
        }


@router.put("/{id}/weights", status_code=status.HTTP_200_OK)
async def update_project_weights(
    id: str,
    request: WeightConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update (or create) WeightConfig for project.
    Deactivates any existing active config and creates a new one.

    Returns:
        Created WeightConfig
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Deactivate existing active configs
    existing_result = await db.execute(
        select(WeightConfig).where(WeightConfig.project_id == id, WeightConfig.is_active)
    )
    existing_configs = existing_result.scalars().all()
    for config in existing_configs:
        config.is_active = False

    # Create new config
    new_config = WeightConfig(
        project_id=id,
        name="custom",
        is_active=True,
        config=request.config,
        yes_threshold=request.yes_threshold,
        created_by=user.id,
    )

    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    return {
        "id": new_config.id,
        "project_id": new_config.project_id,
        "name": new_config.name,
        "is_active": new_config.is_active,
        "config": new_config.config,
        "yes_threshold": new_config.yes_threshold,
        "created_at": new_config.created_at.isoformat(),
    }


@router.get("/{id}/phases", status_code=status.HTTP_200_OK)
async def get_project_phase_config(
    id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get active PhaseConfig for project.
    If none exists, returns default buffer configuration.

    Returns:
        PhaseConfig or default phase buffers
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch active phase config
    config_result = await db.execute(select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active))
    phase_config = config_result.scalars().first()

    if phase_config:
        return {
            "id": phase_config.id,
            "project_id": phase_config.project_id,
            "is_active": phase_config.is_active,
            "config": phase_config.config,
            "sprint_length_weeks": phase_config.sprint_length_weeks,
            "created_at": phase_config.created_at.isoformat(),
            "source": "project_override",
        }
    else:
        # Return default buffers
        return {
            "id": None,
            "project_id": id,
            "is_active": True,
            "config": DEFAULT_BUFFERS,
            "sprint_length_weeks": 2,
            "created_at": None,
            "source": "default",
        }


@router.put("/{id}/phases", status_code=status.HTTP_200_OK)
async def update_project_phase_config(
    id: str,
    request: PhaseConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update (or create) PhaseConfig for project.
    Deactivates any existing active config and creates a new one.

    Returns:
        Created PhaseConfig
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Deactivate existing active configs
    existing_result = await db.execute(select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active))
    existing_configs = existing_result.scalars().all()
    for config in existing_configs:
        config.is_active = False

    # Create new config
    new_config = PhaseConfig(
        project_id=id,
        is_active=True,
        config=request.config,
        sprint_length_weeks=request.sprint_length_weeks,
    )

    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    return {
        "id": new_config.id,
        "project_id": new_config.project_id,
        "is_active": new_config.is_active,
        "config": new_config.config,
        "sprint_length_weeks": new_config.sprint_length_weeks,
        "created_at": new_config.created_at.isoformat(),
    }
