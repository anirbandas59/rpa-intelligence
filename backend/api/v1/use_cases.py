import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from db.models import StageRun, UseCase, User

router = APIRouter()


class UseCaseCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None


class UseCaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    project_id: str | None = None
    source_platform: str | None = None
    install_status: str | None = None
    s1_latest_run_id: str | None = None
    s2_latest_run_id: str | None = None
    s3_latest_run_id: str | None = None
    s4_latest_run_id: str | None = None


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


def _compute_inputs_hash(inputs: dict) -> str:
    """Compute hash of inputs for staleness detection."""
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def _check_stage_readiness(
    use_case: UseCase,
    stage: str,
    current_inputs: dict,
    latest_run_id: str | None,
    db_session: AsyncSession,
) -> str:
    """Check readiness status for a stage."""
    if latest_run_id is None:
        # No run yet — check if inputs satisfy minimum contract
        if stage == "s1":
            if current_inputs.get("name") and current_inputs.get("description"):
                return "ready"
            return "not_ready"
        return "not_ready"

    # Fetch latest run (need to make this sync check — for now simplified)
    # In real implementation, this should be awaited outside
    return "complete"  # Simplified for now


@router.get("/{id}/readiness")
async def get_readiness(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get readiness status for all stages.
    Returns: complete|stale|running|ready|not_ready per stage.
    """
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Use case not found")

    async def check_stage(stage: str, inputs_key: str, latest_run_id_key: str) -> str:
        """Check status for a single stage."""
        current_inputs = getattr(use_case, inputs_key, {})

        # Add top-level fields for S1
        if stage == "s1":
            current_inputs = {
                "name": use_case.name,
                "description": use_case.description,
                "source_platform": use_case.source_platform,
                "install_status": use_case.install_status,
                **current_inputs,
            }

        latest_run_id = getattr(use_case, latest_run_id_key)

        if latest_run_id is None:
            # No run yet — check minimum input contract
            if stage == "s1":
                if use_case.name and use_case.description:
                    return "ready"
                return "not_ready"
            elif stage == "s2":
                if current_inputs:
                    return "ready"
                return "not_ready"
            return "not_ready"

        # Fetch latest run
        run_result = await db.execute(select(StageRun).where(StageRun.id == latest_run_id))
        latest_run = run_result.scalar_one_or_none()

        if not latest_run:
            return "not_ready"

        if latest_run.status == "running":
            return "running"

        if latest_run.status == "failed":
            return "not_ready"

        # Check staleness
        current_hash = _compute_inputs_hash(current_inputs)
        if current_hash != latest_run.inputs_hash:
            return "stale"

        return "complete"

    s1_status = await check_stage("s1", "s1_inputs", "s1_latest_run_id")
    s2_status = await check_stage("s2", "s2_inputs", "s2_latest_run_id")
    s3_phase_calc_status = await check_stage("s3", "s3_inputs", "s3_latest_run_id")
    s4_status = await check_stage("s4", "s4_inputs", "s4_latest_run_id")

    # Stage 3 two-job pattern: separate status for phase_calculator and task_extraction
    s3_inputs = use_case.s3_inputs or {}
    task_extraction_data = s3_inputs.get("task_extraction", {})
    task_extraction_status = task_extraction_data.get("extraction_status", "not_ready")

    return {
        "s1": s1_status,
        "s2": s2_status,
        "s3": s3_phase_calc_status,
        "s3_phase_calculator": s3_phase_calc_status,
        "s3_task_extraction": task_extraction_status,
        "s4": s4_status,
    }
