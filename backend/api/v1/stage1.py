"""
Stage 1 (Migration Assessment) API routes for RPA Intelligence Platform.

Provides endpoints for managing migration assessment workflow: input updates,
run creation, result retrieval, score overrides, and S2 backfill integration.
All assessment runs execute asynchronously via background tasks.

Key endpoints:
- PATCH /{use_case_id}/s1/inputs: Update assessment inputs (name, description, platform)
- POST /{use_case_id}/s1/runs: Create new assessment run (async via background task)
- GET /{use_case_id}/s1/runs: List all runs for a use case
- GET /{use_case_id}/s1/runs/{run_id}: Get single run with full details
- POST /{use_case_id}/s1/override: Override scores without creating new run
- POST /{use_case_id}/s1/backfill-from-s2: Generate suggestions from S2 complexity data

Assessment flow:
1. User updates s1 inputs via PATCH endpoint
2. User triggers run via POST /runs (returns immediately, processing in background)
3. Frontend polls GET /runs/{run_id} until status is "complete"
4. User can override scores via POST /override (preserves audit trail with reason)
5. Optional: user can backfill from S2 complexity for refined scoring suggestions
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, get_session_maker
from core.exceptions import ScoringValidationError
from db.models import StageRun, UseCase, User
from services.assessment_service import AssessmentService

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateS1InputsRequest(BaseModel):
    """Request model for updating Stage 1 inputs on a use case."""

    name: str | None = None
    description: str | None = None
    source_platform: str | None = None
    install_status: str | None = None


class CreateS1RunRequest(BaseModel):
    """Request model for creating a new Stage 1 assessment run."""

    model: str = "claude-haiku-4-5"


class OverrideS1Request(BaseModel):
    """
    Request model for overriding Stage 1 scores without creating a new run.

    Requires a reason for audit trail. Scores are recalculated and migration
    decision is automatically re-derived from the new total score.
    """

    technical_feasibility: int | None = None
    migration_effort: int | None = None
    platform_suitability: int | None = None
    risk: int | None = None
    reason: str


class S1RunResponse(BaseModel):
    """Response model for Stage 1 run creation."""

    run_id: str
    status: str
    run_number: int


async def _execute_s1_background_task(
    use_case_id: str,
    model: str,
    db_factory,
):
    """
    Execute Stage 1 assessment in background task with independent database session.

    Creates its own database session to avoid transaction conflicts with the
    request handler. Delegates to AssessmentService for LLM-based scoring and
    decision derivation. Updates StageRun record on completion or failure.

    Args:
        use_case_id: UseCase ID to assess
        model: LLM model name (e.g., "claude-haiku-4-5")
        db_factory: Async session factory for creating independent database session

    Raises:
        Exception: Re-raises any exception after logging for error tracking
    """
    async with db_factory() as session:
        try:
            service = AssessmentService(session, model=model)
            await service.run_assessment(use_case_id)
        except Exception:
            logger.exception(f"Error in S1 assessment for use case {use_case_id}")
            raise


@router.patch("/{use_case_id}/s1/inputs")
async def update_s1_inputs(
    use_case_id: str,
    request: UpdateS1InputsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update Stage 1 inputs on UseCase (name, description, platform, install status).

    Updates top-level UseCase fields used as assessment inputs. Does not trigger
    a new assessment run automatically. Only provided fields are updated (partial update).

    Args:
        use_case_id: UseCase ID to update
        request: Partial update request with optional fields
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Confirmation message with use_case_id

    Raises:
        HTTPException: 404 if use case not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Update only provided fields (partial update pattern)
    if request.name is not None:
        use_case.name = request.name
    if request.description is not None:
        use_case.description = request.description
    if request.source_platform is not None:
        use_case.source_platform = request.source_platform
    if request.install_status is not None:
        use_case.install_status = request.install_status

    await db.commit()
    await db.refresh(use_case)

    return {"status": "updated", "use_case_id": use_case_id}


@router.post("/{use_case_id}/s1/runs", response_model=S1RunResponse)
async def create_s1_run(
    use_case_id: str,
    request: CreateS1RunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    db_factory=Depends(get_session_maker),
):
    """
    Create Stage 1 assessment run and execute in background.

    Returns immediately with placeholder response. Actual assessment runs
    asynchronously via background task. Frontend should poll GET /runs/{run_id}
    to check completion status.

    Args:
        use_case_id: UseCase ID to assess
        request: Model selection for assessment (default: claude-haiku-4-5)
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        user: Current authenticated user (injected)
        db_factory: Session factory for background task's independent session (injected)

    Returns:
        S1RunResponse with placeholder run_id and status="running"

    Raises:
        HTTPException: 404 if use case not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Fire background task with session factory (not request session)
    background_tasks.add_task(
        _execute_s1_background_task,
        use_case_id=use_case_id,
        model=request.model,
        db_factory=db_factory,
    )

    # Return immediately with placeholder (actual run creation happens in background)
    return S1RunResponse(
        run_id="pending",
        status="running",
        run_number=1,
    )


@router.get("/{use_case_id}/s1/runs")
async def list_s1_runs(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    List all Stage 1 runs for a use case, ordered by most recent first.

    Returns summary view of all assessment runs including status, scores, and metadata.
    Useful for version history and comparison across runs.

    Args:
        use_case_id: UseCase ID to list runs for
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        List of run summaries with id, run_number, status, timestamps, model, and result
    """
    result = await db.execute(
        select(StageRun)
        .where(StageRun.use_case_id == use_case_id, StageRun.stage == "s1")
        .order_by(StageRun.created_at.desc())
    )
    runs = result.scalars().all()

    return [
        {
            "id": run.id,
            "run_number": run.run_number,
            "status": run.status,
            "created_at": run.created_at,
            "model_used": run.model_used,
            "result": run.result,
        }
        for run in runs
    ]


@router.get("/{use_case_id}/s1/runs/{run_id}")
async def get_s1_run(
    use_case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get single Stage 1 run with full details including inputs snapshot and result.

    Returns complete run record for detailed inspection, version comparison, or
    debugging. Includes inputs_hash for staleness detection.

    Args:
        use_case_id: UseCase ID owning the run
        run_id: StageRun ID to retrieve
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Full StageRun record with all fields

    Raises:
        HTTPException: 404 if run not found or doesn't belong to this use case
    """
    result = await db.execute(
        select(StageRun).where(
            StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s1"
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="StageRun not found")

    return {
        "id": run.id,
        "run_number": run.run_number,
        "status": run.status,
        "created_at": run.created_at,
        "model_used": run.model_used,
        "inputs_snapshot": run.inputs_snapshot,
        "inputs_hash": run.inputs_hash,
        "result": run.result,
        "error_message": run.error_message,
    }


@router.post("/{use_case_id}/s1/override")
async def override_s1_decision(
    use_case_id: str,
    request: OverrideS1Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Override Stage 1 scores without creating a new run (preserves audit trail with reason).

    Allows manual score adjustments when AI assessment needs correction. Updates
    the latest StageRun's result in-place, recalculates total score, and auto-derives
    migration decision from new total. Requires a reason for compliance and audit.

    Args:
        use_case_id: UseCase ID to override scores for
        request: Override request with optional dimension scores and required reason
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Updated result with new scores, total, decision, and override metadata

    Raises:
        HTTPException: 404 if use case or latest run not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case or not use_case.s1_latest_run_id:
        raise HTTPException(status_code=404, detail="No assessment found to override")

    run_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s1_latest_run_id))
    stage_run = run_result.scalar_one_or_none()

    if not stage_run:
        raise HTTPException(status_code=404, detail="Latest run not found")

    # Apply overrides to result (partial update, preserving other fields)
    result_data = dict(stage_run.result)

    if request.technical_feasibility is not None:
        result_data["technical_feasibility"] = request.technical_feasibility
    if request.migration_effort is not None:
        result_data["migration_effort"] = request.migration_effort
    if request.platform_suitability is not None:
        result_data["platform_suitability"] = request.platform_suitability
    if request.risk is not None:
        result_data["risk"] = request.risk

    # Recalculate total score from all four dimensions
    result_data["total_score"] = (
        result_data.get("technical_feasibility", 0)
        + result_data.get("migration_effort", 0)
        + result_data.get("platform_suitability", 0)
        + result_data.get("risk", 0)
    )

    # Auto-derive migration_decision from new total_score (QUICK_WIN, STRATEGIC, HOLD, DO_NOT_MIGRATE)
    from core.assessment.decision_utils import derive_migration_decision

    result_data["migration_decision"] = derive_migration_decision(result_data["total_score"])

    # Add override metadata for audit trail
    result_data["override_reason"] = request.reason
    result_data["override_by"] = user.id

    stage_run.result = result_data
    await db.commit()

    logger.info(f"Override applied to S1 run {stage_run.id} by {user.email}: {request.reason}")

    return {"status": "overridden", "run_id": stage_run.id, "result": result_data}


@router.post("/{use_case_id}/s1/backfill-from-s2")
async def backfill_from_s2(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Generate Stage 1 score suggestions from Stage 2 complexity data using Sonnet.

    Uses detailed complexity analysis from S2 (attribute weights, complexity class,
    effort estimates) to generate informed S1 score suggestions. Returns suggestions
    only - does not auto-apply. User must review and manually apply via override endpoint.

    Args:
        use_case_id: UseCase ID to generate suggestions for
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Suggestions dict with proposed scores for four dimensions (technical_feasibility,
        migration_effort, platform_suitability, risk)

    Raises:
        HTTPException: 400 if S1 or S2 runs missing/incomplete, 404 if use case not found
        ScoringValidationError: If S2 result missing required fields
    """
    # Fetch use-case
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Check S2 latest run
    if not use_case.s2_latest_run_id:
        raise HTTPException(status_code=400, detail="No S2 complexity data available")

    s2_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s2_latest_run_id))
    s2_run = s2_result.scalar_one_or_none()

    if not s2_run or s2_run.status != "complete":
        raise HTTPException(status_code=400, detail="S2 complexity assessment not complete")

    # Check S1 latest run
    if not use_case.s1_latest_run_id:
        raise HTTPException(status_code=400, detail="No S1 assessment to backfill")

    s1_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s1_latest_run_id))
    s1_run = s1_result.scalar_one_or_none()

    if not s1_run:
        raise HTTPException(status_code=404, detail="S1 run not found")

    # Extract S2 and S1 data for prompt construction
    from llm.manager import LLMManager
    from prompts.assessment_prompts import S1_BACKFILL_SYSTEM, S1_BACKFILL_USER

    s2_data = s2_run.result
    s1_data = s1_run.result

    # Validate required S2 fields are present
    complexity_class = s2_data.get("complexity_class")
    if not complexity_class:
        raise ScoringValidationError("S2 run missing required field: complexity_class")

    total_score = s2_data.get("total_score")
    if total_score is None:
        raise ScoringValidationError("S2 run missing required field: total_score")

    attribute_weights = s2_data.get("attribute_weights")
    if not attribute_weights:
        raise ScoringValidationError("S2 run missing required field: attribute_weights")

    user_prompt = S1_BACKFILL_USER.format(
        complexity_class=complexity_class,
        total_score=total_score,
        effort_min=s2_data.get("effort_min_weeks", 0),
        effort_max=s2_data.get("effort_max_weeks", 0),
        activities=attribute_weights.get("activities", ""),
        business_rules=attribute_weights.get("business_rules", ""),
        layouts=attribute_weights.get("layouts", ""),
        interfaces=attribute_weights.get("interfaces", ""),
        technology=attribute_weights.get("technology", ""),
        current_tf=s1_data.get("technical_feasibility", 0),
        current_me=s1_data.get("migration_effort", 0),
        current_ps=s1_data.get("platform_suitability", 0),
        current_risk=s1_data.get("risk", 0),
    )

    llm = LLMManager(provider_name="anthropic", model_name="claude-sonnet-4-5")

    try:
        raw_response = llm.complete(
            prompt=user_prompt,
            system=S1_BACKFILL_SYSTEM,
            max_tokens=1500,
            temperature=0.3,
        )

        # Parse JSON
        service = AssessmentService(db, model="claude-sonnet-4-5")
        suggestions = service._parse_json_response(raw_response)

        logger.info(f"Generated S1 backfill suggestions for use-case {use_case_id}")

        return {
            "status": "suggestions_generated",
            "suggestions": suggestions,
            "note": "Review and manually apply these suggestions via the"
            " override endpoint if appropriate.",
        }

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")
