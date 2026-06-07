"""
Stage 4 (Sprint Tracker) API routes for RPA Intelligence Platform.

Provides endpoints for sprint tracker workflow: feature decomposition via Sonnet,
deterministic bin-packing for sprint assignment, and Excel export with formula templates.
All runs execute asynchronously via background tasks.

Key endpoints:
- PATCH /{use_case_id}/s4/inputs: Update sprint config (sprint_count, capacity)
- POST /{use_case_id}/s4/runs: Create tracker run (async, returns run_id immediately)
- GET /{use_case_id}/s4/runs: List all tracker runs
- GET /{use_case_id}/s4/runs/{run_id}: Get single run with WBS rows
- GET /{use_case_id}/s4/runs/{run_id}/export: Download Excel tracker file
- POST /{use_case_id}/s4/load-from-s2: Copy complexity and process description
- POST /{use_case_id}/s4/load-from-s3: Copy sprint count from timeline

Tracker flow:
1. User provides sprint_count (or loads from S3 via POST /load-from-s3)
2. User triggers run via POST /runs (returns immediately, processing in background)
3. Backend runs tracker_agent: groups S3 task_extraction → WBS rows with sprint assignment
4. Deterministic bin-packing assigns rows to sprints within Build+SIT window
5. User exports via GET /export → openpyxl fills template with formulas
"""

import hashlib
import json
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agents.tracker_agent import run_tracker_agent
from api.dependencies import get_current_user, get_db
from db.models import StageRun, UseCase, User
from db.session import get_session_factory
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
    task_extraction: dict,
    total_effort_hours: float,
    build_sit_window: dict,
    complexity_class: str,
    effort_weeks: int,
    sprint_count: int,
    sprint_capacity: int,
):
    """
    Execute tracker agent in background with independent database session.

    Runs tracker_agent (Sonnet + LangGraph) to group S3 task extraction into WBS rows,
    then deterministic bin-packing for sprint assignment within Build+SIT window.
    Updates StageRun to "complete" or "failed" based on outcome.

    Args:
        run_id: StageRun ID to update
        use_case_id: UseCase ID being processed
        use_case_name: Process name for context
        task_extraction: Task extraction result from S3 (activities with hours)
        total_effort_hours: Total effort constraint for validation
        build_sit_window: Dict with start_date and end_date from S3
        complexity_class: Complexity class for context
        effort_weeks: Effort in weeks for context
        sprint_count: Number of sprints for bin-packing
        sprint_capacity: Story points per sprint
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            logger.info(f"[S4] Starting tracker agent for run {run_id}")

            result = await run_tracker_agent(
                use_case_id=use_case_id,
                process_name=use_case_name,
                task_extraction=task_extraction,
                total_effort_hours=total_effort_hours,
                build_sit_window=build_sit_window,
                complexity_class=complexity_class,
                effort_weeks=effort_weeks,
                session_id=run_id,
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
                flag_modified(run, "result")
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
    flag_modified(use_case, "s4_inputs")
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
    """
    Create Stage 4 sprint tracker run - async execution via background task.

    Requires S3 task_extraction to be "complete" or "synthesized". Extracts Build+SIT
    window from S3 timeline, then runs tracker_agent in background. Returns immediately
    with run_id and status="running". Frontend polls GET /runs/{run_id} for completion.

    Args:
        use_case_id: UseCase ID to create tracker for
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with run_id and status="running"

    Raises:
        HTTPException: 404 if use case or S3 run not found,
                      400 if sprint_count missing or S3 task_extraction incomplete
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s4_inputs or {}
    s3_inputs = use_case.s3_inputs or {}

    # Validate minimum inputs
    if "sprint_count" not in inputs:
        raise HTTPException(status_code=400, detail="sprint_count required in s4_inputs")

    # Get task_extraction from Stage 3
    task_extraction = s3_inputs.get("task_extraction")
    valid_statuses = ["complete", "synthesized"]  # Accept both document extraction and synthesis

    if not task_extraction or task_extraction.get("extraction_status") not in valid_statuses:
        current_status = task_extraction.get("extraction_status") if task_extraction else "missing"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stage 3 task extraction must have status in {valid_statuses} "
                f"before running Stage 4. Current status: {current_status}"
            ),
        )

    sprint_count = inputs["sprint_count"]
    sprint_capacity = inputs.get("sprint_capacity", 8)

    # Get complexity and effort (prefer from inputs, fallback to S3 or S2)
    complexity_class = inputs.get("complexity_class") or s3_inputs.get("complexity_class", "M")
    effort_weeks = inputs.get("effort_weeks") or s3_inputs.get("effort_weeks", 6)
    total_effort_hours = effort_weeks * 40

    # Get build+SIT window from S3
    if not use_case.s3_latest_run_id:
        raise HTTPException(
            status_code=400, detail="Stage 3 must be complete before running Stage 4"
        )

    s3_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s3_latest_run_id))
    s3_run = s3_result.scalar_one_or_none()
    if not s3_run:
        raise HTTPException(status_code=404, detail="Stage 3 run not found")

    # Extract build+SIT window from S3 phases
    s3_phases = s3_run.result.get("phases", [])
    build_phase = next((p for p in s3_phases if p["name"].lower() == "build"), None)
    sit_phase = next((p for p in s3_phases if p["name"].lower() == "sit"), None)

    if not build_phase or not sit_phase:
        raise HTTPException(
            status_code=400, detail="Build and SIT phases not found in Stage 3 result"
        )

    build_sit_window = {
        "start_date": build_phase["start_date"],
        "end_date": sit_phase["end_date"],
    }

    # Compute run number
    count_result = await db.execute(
        select(func.count(StageRun.id)).where(
            StageRun.use_case_id == use_case_id, StageRun.stage == "s4"
        )
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
        task_extraction=task_extraction,
        total_effort_hours=total_effort_hours,
        build_sit_window=build_sit_window,
        complexity_class=complexity_class,
        effort_weeks=effort_weeks,
        sprint_count=sprint_count,
        sprint_capacity=sprint_capacity,
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
        select(StageRun).where(
            StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s4"
        )
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
    """
    Export Stage 4 tracker run as Excel file with formula templates.

    Generates Excel workbook from output_template.xlsx with 3 sheets: Dashboard,
    Tracker, Project Details. Fills WBS rows with data but preserves formulas for
    SP calculations and Dev Status lookups. Only works on completed runs.

    Args:
        use_case_id: UseCase ID owning the run
        run_id: StageRun ID to export
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        StreamingResponse with Excel file attachment

    Raises:
        HTTPException: 404 if use case or run not found, 400 if run not complete,
                      500 if Excel generation fails
    """
    # Get use case
    uc_result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = uc_result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    # Get S4 run
    s4_result = await db.execute(
        select(StageRun).where(
            StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s4"
        )
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
    flag_modified(use_case, "s4_inputs")
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
    flag_modified(use_case, "s4_inputs")
    use_case.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Loaded S3 data into S4 inputs for use case {use_case_id}")

    return {
        "message": "Stage 3 data loaded into Stage 4 inputs",
        "s4_inputs": inputs,
        "derived_sprint_count": sprint_count,
    }
