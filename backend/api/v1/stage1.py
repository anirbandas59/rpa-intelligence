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

import hashlib
import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, get_redis, get_session_maker
from core.batch_scorer import BatchScorer
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
    run_id: str,
    use_case_id: str,
    model: str,
    db_factory,
):
    """
    Execute Stage 1 assessment in background task with independent database session.

    Creates its own database session to avoid transaction conflicts with the
    request handler. Delegates to AssessmentService for LLM-based scoring and
    decision derivation. Updates existing StageRun record on completion or failure.

    Args:
        run_id: StageRun ID to update (already created by endpoint)
        use_case_id: UseCase ID to assess
        model: LLM model name (e.g., "claude-haiku-4-5")
        db_factory: Async session factory for creating independent database session

    Raises:
        Exception: Re-raises any exception after logging for error tracking
    """
    async with db_factory() as session:
        try:
            service = AssessmentService(session, model=model)
            await service.run_assessment_with_existing_run(run_id, use_case_id)
        except Exception:
            logger.exception(f"Error in S1 assessment for use case {use_case_id}, run {run_id}")
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

    Returns immediately with run_id and status="running". Actual assessment runs
    asynchronously via background task. Frontend should poll GET /readiness
    to check completion status.

    Args:
        use_case_id: UseCase ID to assess
        request: Model selection for assessment (default: claude-haiku-4-5)
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        user: Current authenticated user (injected)
        db_factory: Session factory for background task's independent session (injected)

    Returns:
        S1RunResponse with run_id and status="running"

    Raises:
        HTTPException: 404 if use case not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Compute inputs snapshot and hash
    inputs = {
        "name": use_case.name,
        "description": use_case.description,
        "source_platform": use_case.source_platform,
        "install_status": use_case.install_status,
        **use_case.s1_inputs,
    }
    inputs_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

    # Count existing runs for run_number
    count_result = await db.execute(
        select(StageRun).where(StageRun.use_case_id == use_case_id, StageRun.stage == "s1")
    )
    run_number = len(count_result.scalars().all()) + 1

    # Create StageRun record immediately (before background task)
    stage_run = StageRun(
        use_case_id=use_case_id,
        stage="s1",
        run_number=run_number,
        inputs_snapshot=inputs,
        inputs_hash=inputs_hash,
        result={},
        model_used=request.model,
        status="running",
    )

    db.add(stage_run)
    await db.commit()
    await db.refresh(stage_run)

    # Update use_case.s1_latest_run_id immediately
    use_case.s1_latest_run_id = stage_run.id
    await db.commit()

    logger.info(f"Created S1 StageRun {stage_run.id} for use case {use_case_id}")

    # Fire background task with session factory (not request session)
    background_tasks.add_task(
        _execute_s1_background_task,
        run_id=stage_run.id,
        use_case_id=use_case_id,
        model=request.model,
        db_factory=db_factory,
    )

    # Return immediately with actual run_id
    return S1RunResponse(
        run_id=stage_run.id,
        status="running",
        run_number=run_number,
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


class BatchScoreRequest(BaseModel):
    """Request model for batch scoring multiple use cases."""

    use_case_ids: list[str]
    model: str = "claude-haiku-4-5"


class BatchScoreResponse(BaseModel):
    """Response model for batch scoring request."""

    batch_id: str
    status: str
    total_count: int


class BatchStatusResponse(BaseModel):
    """Response model for batch status polling."""

    batch_id: str
    status: str
    completed_count: int
    total_count: int
    failed_count: int
    errors: dict[str, str]


@router.post("/{project_id}/s1/batch-score", response_model=BatchScoreResponse)
async def batch_score_use_cases(
    project_id: str,
    request: BatchScoreRequest,
    background_tasks: BackgroundTasks,
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    db_factory=Depends(get_session_maker),
):
    """
    Create batch scoring job for multiple use cases with concurrency control.

    Queues multiple use cases for parallel S1 assessment with configurable
    concurrency limit (default: 3 concurrent LLM calls) to prevent overloading
    LLM providers and control costs. Returns immediately with batch_id for
    progress polling. Processing runs in background with Redis-based queue.

    Args:
        project_id: Project ID containing the use cases
        request: List of use case IDs to score and optional model selection
        background_tasks: FastAPI background task scheduler (injected)
        redis: Redis client for queue management (injected)
        db: Database session (injected)
        user: Current authenticated user (injected)
        db_factory: Session factory for background task's independent sessions (injected)

    Returns:
        BatchScoreResponse with batch_id, status="queued", and total_count

    Raises:
        HTTPException: 400 if use_case_ids list is empty
    """
    if not request.use_case_ids:
        raise HTTPException(status_code=400, detail="use_case_ids cannot be empty")

    # Generate unique batch ID
    batch_id = str(uuid.uuid4())

    # Create batch scorer with concurrency limit (3 concurrent LLM calls max)
    scorer = BatchScorer(redis, max_concurrent=3)

    # Create batch in Redis (metadata + queue)
    await scorer.create_batch(batch_id, request.use_case_ids)

    # Fire background task to process batch
    background_tasks.add_task(
        scorer.process_batch,
        batch_id=batch_id,
        db_factory=db_factory,
        model=request.model,
    )

    logger.info(
        f"Batch {batch_id}: Queued {len(request.use_case_ids)} use cases for project {project_id}"
    )

    return BatchScoreResponse(
        batch_id=batch_id,
        status="queued",
        total_count=len(request.use_case_ids),
    )


@router.get("/{project_id}/s1/batch/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    project_id: str,
    batch_id: str,
    redis: aioredis.Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
):
    """
    Get batch scoring progress for frontend polling.

    Returns current status of batch job including completion progress and any errors.
    Frontend should poll this endpoint every 2 seconds until status is "complete".

    Args:
        project_id: Project ID (for route consistency, not used in logic)
        batch_id: Batch identifier to query
        redis: Redis client for queue management (injected)
        user: Current authenticated user (injected)

    Returns:
        BatchStatusResponse with progress counters and error details

    Raises:
        HTTPException: 404 if batch not found
    """
    scorer = BatchScorer(redis)
    status = await scorer.get_batch_status(batch_id)

    if not status:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BatchStatusResponse(
        batch_id=status["batch_id"],
        status=status["status"],
        completed_count=status["completed_count"],
        total_count=status["total_count"],
        failed_count=status["failed_count"],
        errors=status.get("errors", {}),
    )


class SetCurrentRunRequest(BaseModel):
    """Request model for setting a run as current (empty body, run_id in path)."""

    pass


@router.post("/{use_case_id}/s1/runs/{run_id}/set-current")
async def set_current_run(
    use_case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Set a specific run as the current run for display and stats.

    Updates use_case.s1_latest_run_id to point to the selected run. This affects
    which run is used for project-level statistics and default display in UI.
    Useful when user wants to promote an older run back to "current" status.

    Args:
        use_case_id: UseCase ID to update
        run_id: StageRun ID to set as current
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Confirmation message with updated use_case_id and run_id

    Raises:
        HTTPException: 404 if use case or run not found, or run doesn't belong to use case
    """
    # Verify use case exists
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Verify run exists and belongs to this use case
    run_result = await db.execute(
        select(StageRun).where(
            StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s1"
        )
    )
    stage_run = run_result.scalar_one_or_none()

    if not stage_run:
        raise HTTPException(
            status_code=404, detail="Run not found or does not belong to this use case"
        )

    # Update latest_run_id pointer
    use_case.s1_latest_run_id = run_id
    await db.commit()

    logger.info(f"Set S1 current run to {run_id} for use case {use_case_id} by {user.email}")

    return {"status": "updated", "use_case_id": use_case_id, "current_run_id": run_id}


class ExplainOverrideRequest(BaseModel):
    """Request model for generating AI explanation of override."""

    pass


@router.post("/{use_case_id}/s1/explain-override")
async def explain_override(
    use_case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Generate AI explanation of override decision using context + reason + scores.

    Takes existing override metadata (reason, scores) and generates coherent
    explanation using Sonnet. Combines use case context (name, description),
    override reason (can be 1-2 words), and score changes into clear narrative.
    This is optional and on-demand - user clicks "Explain Override" button.

    Args:
        use_case_id: UseCase ID with override to explain
        db: Database session (injected)
        user: Current authenticated user (injected)

    Returns:
        Dict with "explanation" field containing AI-generated text

    Raises:
        HTTPException: 404 if use case or run not found, 400 if no override exists
    """
    # Fetch use case
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case or not use_case.s1_latest_run_id:
        raise HTTPException(status_code=404, detail="UseCase or assessment not found")

    # Fetch latest run
    run_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s1_latest_run_id))
    stage_run = run_result.scalar_one_or_none()

    if not stage_run:
        raise HTTPException(status_code=404, detail="Latest run not found")

    # Check if override exists
    result_data = stage_run.result
    override_reason = result_data.get("override_reason")

    if not override_reason:
        raise HTTPException(status_code=400, detail="No override found to explain")

    # Build context for LLM
    from llm.manager import LLMManager

    system_prompt = """You are an RPA migration specialist. Generate a clear, \
professional explanation of why manual override was applied to an AI assessment.

Given the use case context, override reason, and score changes, write 2-3 \
sentences explaining the override decision in business terms.

Return ONLY the explanation text - no JSON, no markdown, no preamble."""

    user_prompt = f"""Explain this override:

Use Case: {use_case.name}
Description: {use_case.description or 'N/A'}

Override Reason: {override_reason}

Scores After Override:
- Technical Feasibility: {result_data.get('technical_feasibility', 0)}/40
- Migration Effort: {result_data.get('migration_effort', 0)}/25
- Platform Suitability: {result_data.get('platform_suitability', 0)}/20
- Risk: {result_data.get('risk', 0)}/15
- Total: {result_data.get('total_score', 0)}/100
- Decision: {result_data.get('migration_decision', 'N/A')}

Write a clear explanation combining the context, reason, and resulting decision."""

    llm = LLMManager(provider_name="anthropic", model_name="claude-sonnet-4-5")

    try:
        explanation = llm.complete(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=500,
            temperature=0.5,
        )

        logger.info(f"Generated override explanation for use case {use_case_id}")

        return {
            "status": "explanation_generated",
            "explanation": explanation.strip(),
        }

    except Exception as e:
        logger.error(f"Override explanation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")
