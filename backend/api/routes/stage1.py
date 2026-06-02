import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from core.exceptions import ScoringValidationError
from db.models import StageRun, UseCase, User
from services.assessment_service import AssessmentService

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateS1InputsRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    source_platform: str | None = None
    install_status: str | None = None


class CreateS1RunRequest(BaseModel):
    model: str = "claude-haiku-4-5"


class OverrideS1Request(BaseModel):
    technical_feasibility: int | None = None
    migration_effort: int | None = None
    platform_suitability: int | None = None
    risk: int | None = None
    migration_decision: str | None = None
    reason: str


class S1RunResponse(BaseModel):
    run_id: str
    status: str
    run_number: int


@router.patch("/{use_case_id}/s1/inputs")
async def update_s1_inputs(
    use_case_id: str,
    request: UpdateS1InputsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update S1 inputs on UseCase."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Update top-level fields
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
):
    """Create S1 StageRun and execute assessment in background."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Create assessment service and run
    async def run_assessment_task():
        async with db.begin():
            service = AssessmentService(db, model=request.model)
            await service.run_assessment(use_case_id)

    background_tasks.add_task(run_assessment_task)

    # Return immediately with placeholder (actual run creation happens in background)
    # For now, create a placeholder response
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
    """List all S1 StageRuns for a use-case."""
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
    """Get single S1 StageRun with full details."""
    result = await db.execute(
        select(StageRun).where(StageRun.id == run_id, StageRun.use_case_id == use_case_id, StageRun.stage == "s1")
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
    """Update decision/score fields without creating a new run. Requires reason."""
    result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()

    if not use_case or not use_case.s1_latest_run_id:
        raise HTTPException(status_code=404, detail="No assessment found to override")

    run_result = await db.execute(select(StageRun).where(StageRun.id == use_case.s1_latest_run_id))
    stage_run = run_result.scalar_one_or_none()

    if not stage_run:
        raise HTTPException(status_code=404, detail="Latest run not found")

    # Apply overrides to result
    result_data = dict(stage_run.result)

    if request.technical_feasibility is not None:
        result_data["technical_feasibility"] = request.technical_feasibility
    if request.migration_effort is not None:
        result_data["migration_effort"] = request.migration_effort
    if request.platform_suitability is not None:
        result_data["platform_suitability"] = request.platform_suitability
    if request.risk is not None:
        result_data["risk"] = request.risk

    # Recalculate total
    result_data["total_score"] = (
        result_data.get("technical_feasibility", 0)
        + result_data.get("migration_effort", 0)
        + result_data.get("platform_suitability", 0)
        + result_data.get("risk", 0)
    )

    if request.migration_decision is not None:
        result_data["migration_decision"] = request.migration_decision

    # Add override metadata
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
    """Fire Sonnet backfill using S2 data. Returns suggestions without auto-applying."""
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

    # Build backfill prompt
    from llm.manager import LLMManager
    from prompts.assessment_prompts import S1_BACKFILL_SYSTEM, S1_BACKFILL_USER

    s2_data = s2_run.result
    s1_data = s1_run.result

    # Validate required S2 fields
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
            "note": "Review and manually apply these suggestions via the override endpoint if appropriate.",
        }

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")
