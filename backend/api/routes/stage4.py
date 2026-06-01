"""
Stage 4 API routes — Sprint Tracker (Sonnet decompose + deterministic bin-packing).
Async execution pattern with BackgroundTasks.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import json
import logging

from api.dependencies import get_db, get_current_user
from db.models import User, UseCase, StageRun
from agents.tracker_agent import run_tracker_agent
from services.export_service import generate_tracker_xlsx

router = APIRouter()
logger = logging.getLogger(__name__)


class S4InputsUpdate(BaseModel):
    sprint_count: int | None = Field(None, ge=1, description="Number of sprints")
    sprint_capacity: int | None = Field(None, ge=1, description="Story points per sprint")
    process_description_override: str | None = Field(None, description="Manual process description")


class LoadFromS2Request(BaseModel):
    pass  # No parameters needed, just reads latest S2 run


class LoadFromS3Request(BaseModel):
    pass  # No parameters needed, just reads latest S3 run


def compute_inputs_hash(inputs: dict) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


async def run_tracker_background(
    run_id: str,
    use_case_id: str,
    use_case_name: str,
    process_description: str,
    complexity_class: str,
    effort_weeks: int,
    sprint_count: int,
    sprint_capacity: int,
    db: AsyncSession,
):
    """Background task: run tracker agent and update StageRun."""
    try:
        logger.info(f"[S4] Starting tracker agent for run {run_id}")

        result = await run_tracker_agent(
            use_case_id=use_case_id,
            process_name=use_case_name,
            process_description=process_description,
            complexity_class=complexity_class,
            effort_weeks=effort_weeks,
            sprint_count=sprint_count,
            sprint_capacity=sprint_capacity,
        )

        # Update StageRun to complete
        stmt = select(StageRun).where(StageRun.id == run_id)
        db_result = await db.execute(stmt)
        run = db_result.scalar_one_or_none()

        if run:
            run.status = "complete"
            run.result = result
            await db.commit()
            logger.info(f"[S4] Completed run {run_id}")

    except Exception as e:
        logger.error(f"[S4] Run {run_id} failed: {e}")

        # Update StageRun to failed
        stmt = select(StageRun).where(StageRun.id == run_id)
        db_result = await db.execute(stmt)
        run = db_result.scalar_one_or_none()

        if run:
            run.status = "failed"
            run.error_message = str(e)
            await db.commit()


@router.patch("/{use_case_id}/s4/inputs")
async def update_s4_inputs(
    use_case_id: str,
    update: S4InputsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update Stage 4 inputs. Does not trigger a run."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s4_inputs or {}

    if update.sprint_count is not None:
        inputs["sprint_count"] = update.sprint_count
    if update.sprint_capacity is not None:
        inputs["sprint_capacity"] = update.sprint_capacity
    if update.process_description_override is not None:
        inputs["process_description"] = update.process_description_override
        inputs["process_description_source"] = "manual"

    use_case.s4_inputs = inputs
    use_case.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(use_case)

    return {"s4_inputs": use_case.s4_inputs}


@router.post("/{use_case_id}/s4/runs")
async def create_s4_run(
    use_case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Stage 4 run — async with background task."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s4_inputs or {}

    # Validate minimum inputs
    if "sprint_count" not in inputs:
        raise HTTPException(status_code=400, detail="sprint_count required in s4_inputs")

    sprint_count = inputs["sprint_count"]
    sprint_capacity = inputs.get("sprint_capacity", 8)

    # Get process description (from inputs or use case)
    process_description = inputs.get("process_description", use_case.description or "")
    if not process_description:
        raise HTTPException(status_code=400, detail="process_description required (from use case or s4_inputs)")

    # Get complexity and effort (prefer from inputs, fallback to S2)
    complexity_class = inputs.get("complexity_class", "M")
    effort_weeks = inputs.get("effort_weeks", 6)

    # Compute run number
    count_result = await db.execute(
        select(func.count(StageRun.id)).where(StageRun.use_case_id == use_case_id, StageRun.stage == "s4")
    )
    run_number = count_result.scalar() + 1

    # Create StageRun with status=running
    stage_run = StageRun(
        use_case_id=use_case_id,
        stage="s4",
        run_number=run_number,
        inputs_snapshot=inputs,
        inputs_hash=compute_inputs_hash(inputs),
        result={},
        model_used="claude-sonnet-4-5",
        triggered_by=current_user.id,
        status="running",
    )

    db.add(stage_run)
    use_case.s4_latest_run_id = stage_run.id
    use_case.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(stage_run)

    # Fire background task
    background_tasks.add_task(
        run_tracker_background,
        run_id=stage_run.id,
        use_case_id=use_case_id,
        use_case_name=use_case.name,
        process_description=process_description,
        complexity_class=complexity_class,
        effort_weeks=effort_weeks,
        sprint_count=sprint_count,
        sprint_capacity=sprint_capacity,
        db=db,
    )

    logger.info(f"Created S4 run {stage_run.id} for use case {use_case_id}")

    return {
        "run_id": stage_run.id,
        "status": stage_run.status,
    }


@router.get("/{use_case_id}/s4/runs")
async def list_s4_runs(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all Stage 4 runs for a use case."""
    result = await db.execute(
        select(StageRun)
        .where(StageRun.use_case_id == use_case_id, StageRun.stage == "s4")
        .order_by(StageRun.created_at.desc())
    )
    runs = result.scalars().all()

    return {
        "runs": [
            {
                "id": run.id,
                "run_number": run.run_number,
                "status": run.status,
                "created_at": run.created_at.isoformat(),
                "total_features": run.result.get("metadata", {}).get("total_features"),
                "total_points": run.result.get("metadata", {}).get("total_points"),
                "error_message": run.error_message,
            }
            for run in runs
        ]
    }


@router.get("/{use_case_id}/s4/runs/{run_id}")
async def get_s4_run(
    use_case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single Stage 4 run with full details."""
    result = await db.execute(
        select(StageRun).where(StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s4")
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": run.id,
        "run_number": run.run_number,
        "status": run.status,
        "inputs_snapshot": run.inputs_snapshot,
        "result": run.result,
        "created_at": run.created_at.isoformat(),
        "error_message": run.error_message,
    }


@router.get("/{use_case_id}/s4/runs/{run_id}/export")
async def export_s4_run(
    use_case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export Stage 4 run as Excel file."""
    # Get use case
    uc_result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = uc_result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    # Get S4 run
    s4_result = await db.execute(
        select(StageRun).where(StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s4")
    )
    s4_run = s4_result.scalar_one_or_none()
    if not s4_run:
        raise HTTPException(status_code=404, detail="S4 run not found")

    if s4_run.status != "complete":
        raise HTTPException(status_code=400, detail="Run is not complete yet")

    # Get S2 and S3 runs for export
    s2_run = None
    if use_case.s2_latest_run_id:
        s2_res = await db.execute(select(StageRun).where(StageRun.id == use_case.s2_latest_run_id))
        s2_run = s2_res.scalar_one_or_none()

    s3_run = None
    if use_case.s3_latest_run_id:
        s3_res = await db.execute(select(StageRun).where(StageRun.id == use_case.s3_latest_run_id))
        s3_run = s3_res.scalar_one_or_none()

    # Generate Excel
    s2_data = s2_run.result if s2_run else {}
    s3_data = s3_run.result if s3_run else {"phases": [], "total_weeks": 0}
    s4_data = s4_run.result

    try:
        excel_buffer = generate_tracker_xlsx(
            use_case_name=use_case.name, s2_result=s2_data, s3_result=s3_data, s4_result=s4_data
        )

        filename = f"{use_case.name.replace(' ', '_')}_tracker.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"Export failed for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/{use_case_id}/s4/load-from-s2")
async def load_from_s2(
    use_case_id: str,
    request: LoadFromS2Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Copy process description and complexity from Stage 2 into s4_inputs."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    if not use_case.s2_latest_run_id:
        raise HTTPException(status_code=400, detail="No Stage 2 run found for this use case")

    # Fetch S2 latest run
    s2_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s2_latest_run_id))
    s2_run = s2_result.scalar_one_or_none()
    if not s2_run:
        raise HTTPException(status_code=404, detail="Stage 2 run not found")

    s2_inputs = s2_run.inputs_snapshot
    s2_output = s2_run.result

    # Update s4_inputs
    inputs = use_case.s4_inputs or {}

    # Copy process description if available
    if "process_description" in s2_inputs:
        inputs["process_description"] = s2_inputs["process_description"]
        inputs["process_description_source"] = "from_s2"

    # S2 result stores scoring data nested under "scoring" key
    scoring = s2_output.get("scoring", s2_output)

    # Copy complexity class
    if "complexity_class" in scoring:
        inputs["complexity_class"] = scoring["complexity_class"]
        inputs["complexity_class_source"] = "from_s2"

    # Copy effort
    if "effort_max_weeks" in scoring:
        inputs["effort_weeks"] = scoring["effort_max_weeks"]
        inputs["effort_weeks_source"] = "from_s2"

    use_case.s4_inputs = inputs
    use_case.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Loaded S2 data into S4 inputs for use case {use_case_id}")

    return {"message": "Stage 2 data loaded into Stage 4 inputs", "s4_inputs": inputs}


@router.post("/{use_case_id}/s4/load-from-s3")
async def load_from_s3(
    use_case_id: str,
    request: LoadFromS3Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Copy sprint count and timeline from Stage 3 into s4_inputs."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    if not use_case.s3_latest_run_id:
        raise HTTPException(status_code=400, detail="No Stage 3 run found for this use case")

    # Fetch S3 latest run
    s3_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s3_latest_run_id))
    s3_run = s3_result.scalar_one_or_none()
    if not s3_run:
        raise HTTPException(status_code=404, detail="Stage 3 run not found")

    s3_output = s3_run.result

    # Update s4_inputs
    inputs = use_case.s4_inputs or {}

    # Derive sprint count from total weeks (assuming 2-week sprints)
    total_weeks = s3_output.get("total_weeks", 0)
    sprint_count = max(1, round(total_weeks / 2))

    inputs["sprint_count"] = sprint_count
    inputs["sprint_count_source"] = "from_s3"

    # Copy timeline window
    inputs["timeline_start"] = s3_output.get("phases", [{}])[0].get("start_date", "")
    inputs["timeline_end"] = s3_output.get("project_end_date", "")
    inputs["timeline_source"] = "from_s3"

    use_case.s4_inputs = inputs
    use_case.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Loaded S3 data into S4 inputs for use case {use_case_id}")

    return {
        "message": "Stage 3 data loaded into Stage 4 inputs",
        "s4_inputs": inputs,
        "derived_sprint_count": sprint_count,
    }
