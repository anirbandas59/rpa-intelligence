"""
Stage 3 API routes — Delivery Timeline (deterministic, synchronous).
No LLM calls in main flow. Optional narrative generation in background.
"""

import hashlib
import json
import logging
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.dependencies import get_current_user, get_db
from db.models import StageRun, UploadedFile, UseCase, User
from db.session import get_session_factory
from llm.manager import LLMManager
from prompts.timeline_prompts import S3_NARRATIVE_SYSTEM, S3_NARRATIVE_USER
from services.timeline_service import calculate_timeline

router = APIRouter()
logger = logging.getLogger(__name__)


class S3InputsUpdate(BaseModel):
    effort_weeks: int | None = Field(None, ge=1, description="Build effort in weeks")
    start_date: str | None = Field(None, description="Project start date (ISO format)")
    complexity_class: str | None = Field(None, pattern="^(XS|S|M|L|XL)$")
    buffers: dict | None = Field(None, description="Custom buffer configuration")


class PhaseAdjustment(BaseModel):
    phase_name: str = Field(..., description="Phase name (lowercase): define, design, build, sit, uat, deploy")
    delta_weeks: int = Field(..., description="Adjustment in weeks (can be negative)")


class LoadFromS2Request(BaseModel):
    prefer_max: bool = Field(True, description="Use max_weeks if true, else min_weeks")


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
    """Background task: generate narrative summary with Sonnet."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            llm = LLMManager()
            phase_list = "\n".join([f"- {p['name']}: {p['start_date']} to {p['end_date']} ({p['weeks']}w)" for p in phases])

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


async def run_task_extraction_background(
    use_case_id: str,
    document_path: str,
    process_name: str,
    total_effort_hours: float,
    session_id: str,
):
    """
    Background task: extract tasks with hour-sum constraint via Sonnet.
    Creates its own DB session (request session is closed by the time this runs).
    """
    from agents.task_extraction_agent import run_task_extraction_agent

    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Read document text from file
            with open(document_path, 'r', encoding='utf-8') as f:
                doc_text = f.read()

            # Run task extraction agent
            result = await run_task_extraction_agent(
                use_case_id=use_case_id,
                document_text=doc_text,
                process_name=process_name,
                total_effort_hours=total_effort_hours,
                session_id=session_id,
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
                logger.info(f"Task extraction completed for use case {use_case_id}")

        except Exception as e:
            logger.error(f"Task extraction failed for use case {use_case_id}: {e}")
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
    """Update Stage 3 inputs. Does not trigger a run."""
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
    use_case.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(use_case)

    return {"s3_inputs": use_case.s3_inputs}


@router.post("/{use_case_id}/s3/runs")
async def create_s3_run(
    use_case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Stage 3 run — synchronous, returns timeline immediately."""
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
    use_case.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(stage_run)

    # CRITICAL PREREQUISITE: S2 must be complete with process_summary
    if not use_case.s2_latest_run_id:
        raise HTTPException(
            status_code=400,
            detail="Stage 2 must be complete before running Stage 3. S2 provides complexity and process summary required for task extraction.",
        )

    s2_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s2_latest_run_id))
    s2_run = s2_result.scalar_one_or_none()
    if not s2_run or not s2_run.result.get("process_summary"):
        raise HTTPException(
            status_code=400,
            detail="Stage 2 process summary is required. Re-run S2 with updated extraction to capture process details.",
        )

    # Check if document exists for this use case (uploaded during S2)
    doc_result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.use_case_id == use_case_id)
        .where(UploadedFile.stage == "s2")
        .order_by(UploadedFile.created_at.desc())
        .limit(1)
    )
    uploaded_doc = doc_result.scalar_one_or_none()

    total_effort_hours = effort_weeks * 40  # hours per week

    if uploaded_doc:
        # Path A: Document exists → run extraction from document (existing logic)
        background_tasks.add_task(
            run_task_extraction_background,
            use_case_id=use_case_id,
            document_path=uploaded_doc.stored_path,
            process_name=use_case.name,
            total_effort_hours=total_effort_hours,
            session_id=stage_run.id,
        )

        task_extraction_status = "pending"

        inputs["task_extraction"] = {
            "extraction_status": "pending",
            "source": "document",
            "activities": [],
            "total_net_hours": 0.0,
            "verification_passed": False,
        }

    else:
        # Path B: No document → MANDATORY synthesis from S2 process_summary
        from agents.task_synthesis_agent import synthesize_task_extraction

        async def run_synthesis_background():
            """Background task for synthesis."""
            from db.session import get_session_maker

            async with get_session_maker()() as session:
                try:
                    synthesis_result = await synthesize_task_extraction(
                        use_case_id=use_case_id,
                        process_summary=s2_run.result["process_summary"],
                        total_effort_hours=total_effort_hours,
                        complexity_class=complexity_class,
                        session_id=stage_run.id,
                    )

                    # Update s3_inputs with synthesis result
                    uc_result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
                    uc = uc_result.scalar_one_or_none()
                    if uc:
                        uc.s3_inputs["task_extraction"] = synthesis_result
                        flag_modified(uc, "s3_inputs")
                        await session.commit()

                    logger.info(f"Task synthesis complete for use case {use_case_id}")

                except Exception as e:
                    logger.error(f"Task synthesis failed for use case {use_case_id}: {e}")
                    # Update status to failed
                    uc_result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
                    uc = uc_result.scalar_one_or_none()
                    if uc and "task_extraction" in uc.s3_inputs:
                        uc.s3_inputs["task_extraction"]["extraction_status"] = "failed"
                        uc.s3_inputs["task_extraction"]["error"] = str(e)
                        flag_modified(uc, "s3_inputs")
                        await session.commit()

        background_tasks.add_task(run_synthesis_background)
        task_extraction_status = "synthesizing"

        inputs["task_extraction"] = {
            "extraction_status": "pending",
            "source": "s2_summary",
            "activities": [],
            "total_net_hours": 0.0,
            "verification_passed": False,
        }

    use_case.s3_inputs = inputs
    flag_modified(use_case, "s3_inputs")
    await db.commit()

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
        "task_extraction_status": task_extraction_status,
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
    use_case.updated_at = datetime.utcnow()
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
    use_case.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Phase deltas cleared", "s3_inputs": inputs}


@router.post("/{use_case_id}/s3/load-from-s2")
async def load_from_s2(
    use_case_id: str,
    request: LoadFromS2Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Copy effort and complexity class from Stage 2 latest run into s3_inputs."""
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
    effort_min = scoring.get("effort_min_weeks")
    effort_max = scoring.get("effort_max_weeks")
    complexity_class = scoring.get("complexity_class")

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

    use_case.s3_inputs = inputs
    flag_modified(use_case, "s3_inputs")
    use_case.updated_at = datetime.utcnow()
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
