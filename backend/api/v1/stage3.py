"""
Stage 3 (Delivery Timeline) API routes for RPA Intelligence Platform.

Provides endpoints for delivery timeline calculation and task extraction workflow.
Timeline calculation is deterministic (pure Python, synchronous). Task extraction
runs in background via LangGraph agent with hour-sum constraint enforcement.

Key endpoints:
- PATCH /{use_case_id}/s3/inputs: Update timeline inputs (effort_weeks, start_date, buffers)
- POST /{use_case_id}/s3/runs: Create timeline run (synchronous, returns immediately)
- GET /{use_case_id}/s3/runs: List all timeline runs
- GET /{use_case_id}/s3/runs/{run_id}: Get single run with full phase details
- PATCH /{use_case_id}/s3/phase-delta: Adjust individual phase durations
- POST /{use_case_id}/s3/reset-deltas: Clear all phase adjustments
- POST /{use_case_id}/s3/load-from-s2: Copy complexity and effort from Stage 2

Timeline flow:
1. User provides effort_weeks + start_date (or loads from S2 via POST /load-from-s2)
2. User triggers run via POST /runs (returns timeline synchronously)
3. Backend calculates 6 phases (Define/Design/Build/SIT/UAT/Deploy) with buffers
4. Task extraction runs in background (if document exists from S2)
5. Optional narrative summary generated via Sonnet in background (non-blocking)
"""

import hashlib
import json
import logging
from datetime import UTC, date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from langsmith import traceable
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agents.document_agent import process_document
from api.dependencies import get_current_user, get_db
from db.models import StageRun, UploadedFile, UseCase, User
from db.session import get_session_factory
from llm.manager import LLMManager
from prompts.timeline_prompts import S3_NARRATIVE_SYSTEM, S3_NARRATIVE_USER
from services.timeline_service import calculate_timeline

router = APIRouter()
logger = logging.getLogger(__name__)


class S3InputsUpdate(BaseModel):
    """Request model for updating Stage 3 timeline inputs."""

    effort_weeks: int | None = Field(None, ge=1, description="Build effort in weeks")
    start_date: str | None = Field(None, description="Project start date (ISO format YYYY-MM-DD)")
    complexity_class: str | None = Field(None, pattern="^(XS|S|M|L|XL)$", description="Complexity class from S2")
    buffers: dict | None = Field(None, description="Custom buffer configuration (overrides defaults)")


class PhaseAdjustment(BaseModel):
    """Request model for adjusting individual phase durations."""

    phase_name: str = Field(..., description="Phase name (lowercase): define, design, build, sit, uat, deploy")
    delta_weeks: int = Field(..., description="Adjustment in weeks (can be negative)")


class LoadFromS2Request(BaseModel):
    """Request model for loading Stage 2 complexity data into Stage 3 inputs."""

    prefer_max: bool = Field(True, description="Use max_weeks if true, else min_weeks from S2 effort range")


class TaskDecompositionRequest(BaseModel):
    """Request model for triggering task decomposition."""

    force_regenerate: bool = Field(False, description="Force regeneration even if decomposition already complete")


class TaskDecompositionManualEdit(BaseModel):
    """Request model for manually editing task decomposition results."""

    activities: list[dict] = Field(..., description="Manually edited activities list")
    total_net_hours: float = Field(..., description="Total net hours (sum verification)")
    verification_notes: str | None = Field(None, description="Notes about manual edits")


def compute_inputs_hash(inputs: dict) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


async def generate_narrative_background(
    run_id: str,
    use_case_name: str,
    complexity_class: str,
    total_weeks: int,
    build_weeks: int,
    phases: list[dict],
):
    """
    Generate narrative timeline summary using Sonnet in background (optional enhancement).

    Creates executive-friendly summary of timeline phases using LLM. Runs asynchronously
    and updates StageRun.result with "narrative" field. Non-critical - timeline is
    usable without narrative.

    Args:
        run_id: StageRun ID to update with narrative
        use_case_name: Use case name for context
        complexity_class: Complexity class (XS/S/M/L/XL)
        total_weeks: Total project duration
        build_weeks: Build phase duration
        phases: List of phase dicts with name, start_date, end_date, weeks
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            llm = LLMManager()
            phase_list = "\n".join(
                [f"- {p['name']}: {p['start_date']} to {p['end_date']} ({p['weeks']}w)" for p in phases]
            )

            user_prompt = S3_NARRATIVE_USER.format(
                use_case_name=use_case_name,
                complexity_class=complexity_class,
                total_weeks=total_weeks,
                build_weeks=build_weeks,
                phase_list=phase_list,
            )

            narrative = await llm.complete_async(
                prompt=user_prompt,
                system=S3_NARRATIVE_SYSTEM,
                max_tokens=500,
                temperature=0.5,
            )

            # Update StageRun with narrative
            result = await db.execute(select(StageRun).where(StageRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.result["narrative"] = narrative
                flag_modified(run, "result")
                await db.commit()
                logger.info(f"Generated narrative for S3 run {run_id}")
        except Exception as e:
            logger.error(f"Failed to generate narrative for run {run_id}: {e}")


async def run_task_decomposition_background(
    use_case_id: str,
    total_effort_hours: float,
    complexity_class: str,
    session_id: str,
    document_path: str | None = None,
    pasted_text: str | None = None,
    process_summary: dict | None = None,
):
    """
    Run unified task decomposition agent (extraction OR synthesis) in background.

    Runs the unified task_decomposition_agent (Sonnet + LangGraph) to decompose process
    into activities with hours and reusability tags. Automatically chooses extraction
    (if document_text available) or synthesis (from process_summary). Enforces hour-sum
    constraint with configurable tolerance.

    Args:
        use_case_id: UseCase ID to update
        total_effort_hours: Total effort constraint (effort_weeks * 40)
        complexity_class: Complexity class from S2 (XS/S/M/L/XL)
        session_id: Session ID for logging (typically run_id)
        document_path: Path to uploaded document (from S2) - optional
        pasted_text: Pasted process description (from S2) - optional
        process_summary: Process context from Stage 2 - required

    Flow:
    1. Read document text from file OR use pasted_text (if available)
    2. Run unified task_decomposition_agent with hour constraint
    3. Update s3_inputs.task_extraction with result
    4. On failure: mark extraction_status as "failed"
    """
    from agents.task_decomposition_agent import run_task_decomposition

    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Get document text from file or pasted text (optional)
            doc_text = None
            if document_path:
                doc_text = process_document(document_path)
            elif pasted_text:
                doc_text = pasted_text

            # Run unified task decomposition agent
            result = await run_task_decomposition(
                use_case_id=use_case_id,
                total_effort_hours=total_effort_hours,
                complexity_class=complexity_class,
                session_id=session_id,
                document_text=doc_text,
                process_summary=process_summary,
            )

            # Update s3_inputs with result
            uc_result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
            use_case = uc_result.scalar_one_or_none()
            if use_case:
                inputs = use_case.s3_inputs or {}
                inputs["task_extraction"] = result
                use_case.s3_inputs = inputs
                flag_modified(use_case, "s3_inputs")
                await db.commit()
                logger.info(f"Task decomposition completed for use case {use_case_id}")

        except Exception as e:
            logger.error(f"Task decomposition failed for use case {use_case_id}: {e}")
            # Mark as failed in s3_inputs
            uc_result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
            use_case = uc_result.scalar_one_or_none()
            if use_case:
                inputs = use_case.s3_inputs or {}
                inputs["task_extraction"] = {
                    "extraction_status": "failed",
                    "error": str(e),
                }
                use_case.s3_inputs = inputs
                flag_modified(use_case, "s3_inputs")
                await db.commit()


@router.patch("/{use_case_id}/s3/inputs")
async def update_s3_inputs(
    use_case_id: str,
    update: S3InputsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update Stage 3 timeline inputs (effort, start date, complexity, buffers).

    Partial update endpoint for modifying timeline calculation parameters. Does NOT
    trigger a new run automatically - user must call POST /runs after updating inputs.

    Args:
        use_case_id: UseCase ID to update
        update: Partial update request with optional fields
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Updated s3_inputs dict

    Raises:
        HTTPException: 404 if use case not found, 400 if start_date format invalid
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s3_inputs or {}

    if update.effort_weeks is not None:
        inputs["effort_weeks"] = update.effort_weeks
    if update.start_date is not None:
        # Validate date format
        try:
            date.fromisoformat(update.start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format (use YYYY-MM-DD)")
        inputs["start_date"] = update.start_date
    if update.complexity_class is not None:
        inputs["complexity_class"] = update.complexity_class
    if update.buffers is not None:
        inputs["buffers"] = update.buffers

    use_case.s3_inputs = inputs
    flag_modified(use_case, "s3_inputs")
    use_case.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(use_case)

    return {"s3_inputs": use_case.s3_inputs}


@traceable
@router.post("/{use_case_id}/s3/runs")
async def create_s3_run(
    use_case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create Stage 3 timeline run - synchronous calculation, returns timeline immediately.

    Calculates 6-phase delivery timeline (Define/Design/Build/SIT/UAT/Deploy) using pure
    Python date arithmetic. Returns result synchronously in response. Task decomposition
    is now decoupled and triggered via separate endpoint POST /s3/task-decomposition.

    Args:
        use_case_id: UseCase ID to create run for
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with run_id, status="complete", result (timeline with phases), and task_decomposition_required flag

    Raises:
        HTTPException: 404 if use case not found, 400 if required inputs missing,
                      500 if timeline calculation fails
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s3_inputs or {}

    # Validate minimum inputs
    if "effort_weeks" not in inputs:
        raise HTTPException(status_code=400, detail="effort_weeks required in s3_inputs")
    if "start_date" not in inputs:
        raise HTTPException(status_code=400, detail="start_date required in s3_inputs")

    effort_weeks = inputs["effort_weeks"]
    start_date_str = inputs["start_date"]
    complexity_class = inputs.get("complexity_class", "M")
    buffers = inputs.get("buffers")
    phase_deltas = inputs.get("phase_deltas", {})

    # Parse date
    try:
        start_date = date.fromisoformat(start_date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date format")

    # Calculate timeline (pure Python, no LLM)
    try:
        timeline = calculate_timeline(
            build_weeks=effort_weeks,
            start_date=start_date,
            complexity_class=complexity_class,
            buffers=buffers,
            phase_deltas=phase_deltas,
        )
    except Exception as e:
        logger.error(f"Timeline calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Timeline calculation failed: {str(e)}")

    # Compute run number
    count_result = await db.execute(
        select(func.count(StageRun.id)).where(StageRun.use_case_id == use_case_id, StageRun.stage == "s3")
    )
    run_number = count_result.scalar() + 1

    # Create StageRun
    stage_run = StageRun(
        use_case_id=use_case_id,
        stage="s3",
        run_number=run_number,
        inputs_snapshot=inputs,
        inputs_hash=compute_inputs_hash(inputs),
        result=timeline.model_dump(),
        model_used=None,  # No LLM in main flow
        triggered_by=current_user.id,
        status="complete",
    )

    db.add(stage_run)
    await db.flush()  # populates stage_run.id (default=new_uuid fires at INSERT)
    use_case.s3_latest_run_id = stage_run.id
    use_case.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(stage_run)

    # Check if task decomposition is needed
    task_extraction = inputs.get("task_extraction")
    decomposition_required = (
        not task_extraction
        or task_extraction.get("extraction_status") != "complete"
        or not task_extraction.get("verification_passed")
    )

    # Fire narrative generation in background (optional)
    background_tasks.add_task(
        generate_narrative_background,
        run_id=stage_run.id,
        use_case_name=use_case.name,
        complexity_class=complexity_class,
        total_weeks=timeline.total_weeks,
        build_weeks=effort_weeks,
        phases=timeline.phases,
    )

    logger.info(f"Created S3 run {stage_run.id} for use case {use_case_id}")

    return {
        "run_id": stage_run.id,
        "status": stage_run.status,
        "result": stage_run.result,
        "task_decomposition_required": decomposition_required,
        "message": "Timeline calculated. Trigger task decomposition separately if needed." if decomposition_required else "Timeline calculated.",
    }


@router.get("/{use_case_id}/s3/runs")
async def list_s3_runs(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all Stage 3 runs for a use case."""
    result = await db.execute(
        select(StageRun)
        .where(StageRun.use_case_id == use_case_id, StageRun.stage == "s3")
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
                "total_weeks": run.result.get("total_weeks"),
                "project_end_date": run.result.get("project_end_date"),
            }
            for run in runs
        ]
    }


@router.get("/{use_case_id}/s3/runs/{run_id}")
async def get_s3_run(
    use_case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single Stage 3 run with full details."""
    result = await db.execute(
        select(StageRun).where(StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s3")
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": run.id,
        "run_number": run.run_number,
        "status": run.status,
        "inputs_snapshot": run.inputs_snapshot,
        "inputs_hash": run.inputs_hash,
        "result": run.result,
        "created_at": run.created_at.isoformat(),
    }


@router.patch("/{use_case_id}/s3/phase-delta")
async def adjust_phase(
    use_case_id: str,
    adjustment: PhaseAdjustment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply phase adjustment (delta weeks). Stored in s3_inputs, not a new run."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    valid_phases = {"define", "design", "build", "sit", "uat", "deploy"}
    if adjustment.phase_name.lower() not in valid_phases:
        raise HTTPException(status_code=400, detail=f"Invalid phase name. Must be one of: {valid_phases}")

    inputs = use_case.s3_inputs or {}
    phase_deltas = inputs.get("phase_deltas", {})
    phase_deltas[adjustment.phase_name.lower()] = adjustment.delta_weeks
    inputs["phase_deltas"] = phase_deltas

    use_case.s3_inputs = inputs
    flag_modified(use_case, "s3_inputs")
    use_case.updated_at = datetime.now(UTC)
    await db.commit()

    return {"phase_deltas": phase_deltas}


@router.post("/{use_case_id}/s3/reset-deltas")
async def reset_phase_deltas(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all phase deltas from s3_inputs."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    inputs = use_case.s3_inputs or {}
    if "phase_deltas" in inputs:
        del inputs["phase_deltas"]

    use_case.s3_inputs = inputs
    use_case.updated_at = datetime.now(UTC)
    await db.commit()

    return {"message": "Phase deltas cleared", "s3_inputs": inputs}


@router.post("/{use_case_id}/s3/generate-narrative")
async def generate_narrative(
    use_case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate narrative summary for latest S3 run (user-triggered).

    Returns immediately with status, narrative generation runs in background.
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    if not use_case.s3_latest_run_id:
        raise HTTPException(status_code=400, detail="No S3 run found. Run timeline first.")

    # Fetch latest run
    run_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s3_latest_run_id))
    latest_run = run_result.scalar_one_or_none()
    if not latest_run or latest_run.status != "complete":
        raise HTTPException(status_code=400, detail="Latest S3 run not complete")

    result_data = latest_run.result or {}
    phases = result_data.get("phases", [])
    total_weeks = result_data.get("total_weeks", 0)

    # Get build phase weeks
    build_weeks = next((p["weeks"] for p in phases if "build" in p["name"].lower()), 0)

    # Get complexity class from inputs
    inputs = use_case.s3_inputs or {}
    complexity_class = inputs.get("complexity_class", "M")

    # Dispatch background task
    background_tasks.add_task(
        generate_narrative_background,
        run_id=use_case.s3_latest_run_id,
        use_case_name=use_case.name,
        complexity_class=complexity_class,
        total_weeks=total_weeks,
        build_weeks=build_weeks,
        phases=phases,
    )

    return {"status": "generating", "message": "Narrative generation started"}


@router.post("/{use_case_id}/s3/task-decomposition")
async def trigger_task_decomposition(
    use_case_id: str,
    request: TaskDecompositionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger task decomposition for Stage 3 - independent from timeline calculation.

    Runs task_decomposition_agent (unified extraction + synthesis) in background with
    hour-sum constraint enforcement. This endpoint decouples task decomposition from
    timeline calculation, allowing users to regenerate task breakdown without recalculating timeline.

    Args:
        use_case_id: UseCase ID to decompose tasks for
        request: Request with force_regenerate flag
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with status="running" and message

    Raises:
        HTTPException: 404 if use case not found, 400 if prerequisites missing (S2, S3 timeline)
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    # Validate prerequisites
    if not use_case.s3_latest_run_id:
        raise HTTPException(
            status_code=400,
            detail="Stage 3 timeline must be calculated first. Run POST /s3/runs before task decomposition.",
        )

    if not use_case.s2_latest_run_id:
        raise HTTPException(
            status_code=400,
            detail="Stage 2 must be complete before task decomposition. S2 provides process summary.",
        )

    # Fetch S2 run for process_summary
    s2_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s2_latest_run_id))
    s2_run = s2_result.scalar_one_or_none()
    if not s2_run or not s2_run.result.get("process_summary"):
        raise HTTPException(
            status_code=400,
            detail="Stage 2 process summary is required. Re-run S2 to capture process details.",
        )

    # Check if already complete and not forcing regeneration
    s3_inputs = use_case.s3_inputs or {}
    task_extraction = s3_inputs.get("task_extraction")
    if not request.force_regenerate and task_extraction:
        if task_extraction.get("extraction_status") == "complete" and task_extraction.get("verification_passed"):
            return {
                "status": "already_complete",
                "message": "Task decomposition already complete. Use force_regenerate=true to regenerate.",
                "task_extraction": task_extraction,
            }

    # Calculate total effort hours from S3 inputs
    effort_weeks = s3_inputs.get("effort_weeks")
    if not effort_weeks:
        raise HTTPException(status_code=400, detail="effort_weeks not found in S3 inputs")

    total_effort_hours = effort_weeks * 40
    complexity_class = s3_inputs.get("complexity_class", "M")

    # Check data sources
    doc_result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.use_case_id == use_case_id)
        .where(UploadedFile.stage == "s2")
        .order_by(UploadedFile.created_at.desc())
        .limit(1)
    )
    uploaded_doc = doc_result.scalar_one_or_none()
    pasted_text = use_case.s2_inputs.get("pasted_text") if use_case.s2_inputs else None

    if not uploaded_doc and not pasted_text:
        # Fall back to synthesis from S2 summary
        source_type = "s2_summary"
        document_path = None
        pasted_text_data = None
    elif uploaded_doc:
        source_type = "document"
        document_path = uploaded_doc.stored_path
        pasted_text_data = None
    else:
        source_type = "pasted_text"
        document_path = None
        pasted_text_data = pasted_text

    # Mark as running
    s3_inputs["task_extraction"] = {
        "extraction_status": "running",
        "source": source_type,
        "activities": [],
        "total_net_hours": 0.0,
        "verification_passed": False,
    }
    use_case.s3_inputs = s3_inputs
    flag_modified(use_case, "s3_inputs")
    await db.commit()

    # Dispatch background task - unified agent handles both extraction and synthesis
    background_tasks.add_task(
        run_task_decomposition_background,
        use_case_id=use_case_id,
        total_effort_hours=total_effort_hours,
        complexity_class=complexity_class,
        session_id=use_case.s3_latest_run_id,
        document_path=document_path,
        pasted_text=pasted_text_data,
        process_summary=s2_run.result.get("process_summary"),
    )

    logger.info(f"Task decomposition triggered for use case {use_case_id} (source: {source_type})")

    return {
        "status": "running",
        "message": f"Task decomposition started in background (source: {source_type})",
        "source": source_type,
    }


@router.patch("/{use_case_id}/s3/task-decomposition/manual-edit")
async def manual_edit_task_decomposition(
    use_case_id: str,
    edit: TaskDecompositionManualEdit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually edit task decomposition results.

    Allows users to fix validation errors by directly editing activities and hours.
    Updates s3_inputs.task_extraction with manual edits and marks as manually_corrected.

    Args:
        use_case_id: UseCase ID to update
        edit: Manual edit request with activities, hours, and notes
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Updated task_extraction dict

    Raises:
        HTTPException: 404 if use case not found, 400 if task_extraction not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    s3_inputs = use_case.s3_inputs or {}
    if "task_extraction" not in s3_inputs:
        raise HTTPException(status_code=400, detail="No task decomposition found to edit")

    # Verify hour sum
    calculated_hours = sum(
        step.get("weight_hours", 0)
        for activity in edit.activities
        for step in activity.get("steps", [])
        if step.get("reusability") != "full"
    )

    verification_passed = abs(calculated_hours - edit.total_net_hours) < 0.5

    # Update task_extraction with manual edits
    s3_inputs["task_extraction"] = {
        "extraction_status": "complete",
        "source": s3_inputs["task_extraction"].get("source", "manual"),
        "source_modified": "manually_corrected",
        "activities": edit.activities,
        "total_net_hours": edit.total_net_hours,
        "verification_passed": verification_passed,
        "verification_notes": edit.verification_notes or "Manually corrected by user",
        "edited_by": current_user.id,
        "edited_at": datetime.now(UTC).isoformat(),
    }

    use_case.s3_inputs = s3_inputs
    flag_modified(use_case, "s3_inputs")
    use_case.updated_at = datetime.now(UTC)
    await db.commit()

    logger.info(f"Task decomposition manually edited for use case {use_case_id}")

    return {
        "message": "Task decomposition updated with manual edits",
        "task_extraction": s3_inputs["task_extraction"],
    }


@router.get("/{use_case_id}/s3/task-decomposition")
async def get_task_decomposition_status(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current task decomposition status and result.

    Returns the latest task_extraction data from s3_inputs with status information.

    Args:
        use_case_id: UseCase ID to query
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with status and task_extraction data

    Raises:
        HTTPException: 404 if use case not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    s3_inputs = use_case.s3_inputs or {}
    task_extraction = s3_inputs.get("task_extraction")

    if not task_extraction:
        return {
            "status": "not_started",
            "message": "Task decomposition not started yet",
        }

    return {
        "status": task_extraction.get("extraction_status", "unknown"),
        "task_extraction": task_extraction,
    }


@router.post("/{use_case_id}/s3/load-from-s2")
async def load_from_s2(
    use_case_id: str,
    request: LoadFromS2Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Copy effort estimate and complexity class from Stage 2 into Stage 3 inputs.

    Convenience endpoint for data flow from S2 → S3. Extracts effort_min_weeks,
    effort_max_weeks, and complexity_class from latest S2 run and copies to s3_inputs.
    User can choose min or max effort via prefer_max flag.

    Args:
        use_case_id: UseCase ID to load data for
        request: Preference for min vs max effort weeks
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Updated s3_inputs with loaded values and source tags

    Raises:
        HTTPException: 404 if use case or S2 run not found, 400 if S2 data incomplete
    """
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

    s2_output = s2_run.result
    # S2 result may store scoring data at top level or nested under "scoring"
    scoring = s2_output.get("scoring", s2_output)
    process_summary = s2_output.get("process_summary", {})
    effort_min = scoring.get("effort_min_weeks")
    effort_max = scoring.get("effort_max_weeks")
    complexity_class = scoring.get("complexity_class")
    summary = process_summary.get("overall_summary")
    activities = process_summary.get("key_activities")
    business_rules = process_summary.get("key_logical_points")
    target_applications = process_summary.get("key_applications")
    layouts = process_summary.get("key_layouts")
    technologies = process_summary.get("key_additional_technologies")

    if effort_min is None or complexity_class is None:
        raise HTTPException(status_code=400, detail="Stage 2 result incomplete")

    # Choose effort based on preference
    effort_weeks = effort_max if request.prefer_max else effort_min

    # Update s3_inputs
    inputs = use_case.s3_inputs or {}
    inputs["effort_weeks"] = effort_weeks
    inputs["effort_weeks_source"] = "from_s2"
    inputs["complexity_class"] = complexity_class
    inputs["complexity_class_source"] = "from_s2"
    inputs["summary"] = summary
    inputs["activities"] = activities
    inputs["business_rules"] = business_rules
    inputs["target_applications"] = target_applications
    inputs["layouts"] = layouts
    inputs["technologies"] = technologies

    use_case.s3_inputs = inputs
    flag_modified(use_case, "s3_inputs")
    use_case.updated_at = datetime.now(UTC)
    await db.commit()

    logger.info(f"Loaded S2 data into S3 inputs for use case {use_case_id}")

    return {
        "message": "Stage 2 data loaded into Stage 3 inputs",
        "s3_inputs": inputs,
        "loaded_values": {
            "effort_weeks": effort_weeks,
            "complexity_class": complexity_class,
        },
    }
