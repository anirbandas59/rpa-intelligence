"""
Tool registrations — registers all agentic tools with the ToolRegistry.

Call register_all_tools() once at application startup (in lifespan).
All execute functions are async and accept keyword arguments matching the input schema.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from tools.registry import ToolDefinition, ToolRegistry
from tools.schemas import (
    CalculateComplexityInput,
    CalculateComplexityOutput,
    CheckRunStatusInput,
    CheckRunStatusOutput,
    GetStageResultInput,
    GetStageResultOutput,
    QuerySimilarInput,
    QuerySimilarOutput,
    S1AssessmentInput,
    S1AssessmentOutput,
    S2ExtractionInput,
    S2ExtractionOutput,
    S3TimelineInput,
    S3TimelineOutput,
    S4TrackerInput,
    S4TrackerOutput,
    UpdateStageInputsInput,
    UpdateStageInputsOutput,
)

logger = logging.getLogger(__name__)


def register_all_tools() -> None:
    """Register all tools. Call once at startup."""
    _register_run_s1_assessment()
    _register_run_s2_extraction()
    _register_run_s3_timeline()
    _register_run_s4_tracker()
    _register_get_stage_result()
    _register_update_stage_inputs()
    _register_calculate_complexity()
    _register_check_run_status()
    _register_query_similar_use_cases()
    logger.info(f"Registered {len(ToolRegistry.list_all())} tools")


def _register_run_s1_assessment():
    """Register Stage 1 migration assessment tool."""

    async def execute(use_case_id: str, db: AsyncSession) -> S1AssessmentOutput:
        from services.assessment_service import AssessmentService

        svc = AssessmentService(db=db)
        stage_run = await svc.run_assessment(use_case_id)
        return S1AssessmentOutput(
            run_id=stage_run.id,
            status=stage_run.status,
            migration_decision=stage_run.result.get("migration_decision"),
            total_score=stage_run.result.get("total_score"),
        )

    ToolRegistry.register(
        ToolDefinition(
            name="run_s1_assessment",
            description="Run Stage 1 migration assessment for a use-case. Returns decision and score.",
            input_schema=S1AssessmentInput,
            output_schema=S1AssessmentOutput,
        ),
        execute,
    )


def _register_run_s2_extraction():
    """Register Stage 2 complexity extraction and scoring tool."""

    async def execute(
        use_case_id: str,
        db: AsyncSession,
        document_path: str | None = None,
        pasted_text: str | None = None,
        manual_bands: dict[str, str] | None = None,
    ) -> S2ExtractionOutput:
        from agents.orchestrator import run_s2_assessment

        result = await run_s2_assessment(
            use_case_id=use_case_id,
            document_path=document_path,
            pasted_text=pasted_text,
            manual_bands=manual_bands,
            session=db,
        )
        return S2ExtractionOutput(
            run_id=result.get("run_id", ""),
            status=result.get("status", "complete"),
            complexity_class=result.get("complexity_class"),
            total_score=result.get("total_score"),
        )

    ToolRegistry.register(
        ToolDefinition(
            name="run_s2_extraction",
            description="Run Stage 2 complexity extraction and scoring. Accepts document, text, or manual bands.",
            input_schema=S2ExtractionInput,
            output_schema=S2ExtractionOutput,
        ),
        execute,
    )


def _register_run_s3_timeline():
    """Register Stage 3 timeline calculation tool."""

    async def execute(
        use_case_id: str,
        db: AsyncSession,
        effort_weeks: int,
        start_date: str,
        complexity_class: str = "M",
    ) -> S3TimelineOutput:
        from datetime import date

        from services.timeline_service import calculate_timeline

        start = date.fromisoformat(start_date)
        result = calculate_timeline(
            build_weeks=effort_weeks,
            start_date=start,
            complexity_class=complexity_class,
        )
        return S3TimelineOutput(
            run_id=use_case_id,
            status="complete",
            total_weeks=result.total_weeks,
            phase_count=len(result.phases),
        )

    ToolRegistry.register(
        ToolDefinition(
            name="run_s3_timeline",
            description="Calculate Stage 3 delivery timeline. Returns phase breakdown and total weeks.",
            input_schema=S3TimelineInput,
            output_schema=S3TimelineOutput,
        ),
        execute,
    )


def _register_run_s4_tracker():
    """Register Stage 4 sprint tracker tool."""

    async def execute(
        use_case_id: str,
        db: AsyncSession,
        sprint_count: int,
        sprint_capacity: int = 8,
    ) -> S4TrackerOutput:
        from sqlalchemy import select

        from agents.tracker_agent import create_tracker_graph
        from db.models import UseCase

        result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise ValueError(f"UseCase {use_case_id} not found")

        s4_inputs = use_case.s4_inputs or {}
        graph = create_tracker_graph()
        state = await graph.ainvoke(
            {
                "use_case_id": use_case_id,
                "process_name": use_case.name,
                "process_description": use_case.description or "",
                "complexity_class": s4_inputs.get("complexity_class", "M"),
                "effort_weeks": s4_inputs.get("effort_weeks", 5),
                "sprint_count": sprint_count,
                "sprint_capacity": sprint_capacity,
                "document_context": s4_inputs.get("document_context", ""),
                "raw_llm_response": "",
                "extracted_features": [],
                "sprint_assignment": {},
                "error": None,
            }
        )
        features = state.get("extracted_features", [])
        return S4TrackerOutput(
            run_id=use_case_id,
            status="complete",
            feature_count=len(features),
            sprint_count=sprint_count,
        )

    ToolRegistry.register(
        ToolDefinition(
            name="run_s4_tracker",
            description="Run Stage 4 sprint tracker. Decomposes process into features and assigns to sprints.",
            input_schema=S4TrackerInput,
            output_schema=S4TrackerOutput,
        ),
        execute,
    )


def _register_get_stage_result():
    """Register tool to retrieve latest stage run result."""

    async def execute(use_case_id: str, db: AsyncSession, stage: str) -> GetStageResultOutput:
        from sqlalchemy import select

        from db.models import StageRun

        result = await db.execute(
            select(StageRun)
            .where(StageRun.use_case_id == use_case_id, StageRun.stage == stage)
            .order_by(StageRun.created_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if not run:
            return GetStageResultOutput(run_id=None, status="not_run")
        return GetStageResultOutput(
            run_id=run.id,
            status=run.status,
            result=run.result,
        )

    ToolRegistry.register(
        ToolDefinition(
            name="get_stage_result",
            description="Get the latest run result for a stage. Returns status and result dict.",
            input_schema=GetStageResultInput,
            output_schema=GetStageResultOutput,
        ),
        execute,
    )


def _register_update_stage_inputs():
    """Register tool to update stage inputs on a use-case."""

    async def execute(
        use_case_id: str, db: AsyncSession, stage: str, inputs: dict
    ) -> UpdateStageInputsOutput:
        from sqlalchemy import select

        from db.models import UseCase

        result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise ValueError(f"UseCase {use_case_id} not found")

        # Extract stage number from stage string (e.g., "s1" -> "1")
        stage_num = stage.lower().replace("s", "")
        attr_name = f"s{stage_num}_inputs"

        existing = getattr(use_case, attr_name) or {}
        existing.update(inputs)
        setattr(use_case, attr_name, existing)
        await db.commit()
        return UpdateStageInputsOutput(updated=True, use_case_id=use_case_id)

    ToolRegistry.register(
        ToolDefinition(
            name="update_stage_inputs",
            description="Merge new input fields into a stage's inputs dict on a use-case.",
            input_schema=UpdateStageInputsInput,
            output_schema=UpdateStageInputsOutput,
        ),
        execute,
    )


def _register_calculate_complexity():
    """Register deterministic complexity scoring tool."""

    async def execute(
        activities: str, business_rules: str, layouts: str, interfaces: str, technology: str
    ) -> CalculateComplexityOutput:
        from core.scoring.classifier import classify
        from core.scoring.effort_table import get_effort
        from core.scoring.weight_matrix import get_weight, load_weight_matrix

        matrix = load_weight_matrix()
        total = (
            get_weight(matrix, "activities", activities)
            + get_weight(matrix, "business_rules", business_rules)
            + get_weight(matrix, "layouts", layouts)
            + get_weight(matrix, "interfaces", interfaces)
            + get_weight(matrix, "technology", technology)
        )
        cls = classify(total)
        effort = get_effort(cls)
        return CalculateComplexityOutput(
            total_score=total,
            complexity_class=cls,
            effort_min_weeks=effort["min_weeks"],
            effort_max_weeks=effort["max_weeks"],
        )

    ToolRegistry.register(
        ToolDefinition(
            name="calculate_complexity",
            description="Deterministic complexity scoring from 5 attribute bands. No LLM call.",
            input_schema=CalculateComplexityInput,
            output_schema=CalculateComplexityOutput,
        ),
        execute,
    )


def _register_check_run_status():
    """Register tool to check stage run status."""

    async def execute(run_id: str, db: AsyncSession) -> CheckRunStatusOutput:
        from sqlalchemy import select

        from db.models import StageRun

        result = await db.execute(select(StageRun).where(StageRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"StageRun {run_id} not found")
        return CheckRunStatusOutput(run_id=run.id, status=run.status, stage=run.stage)

    ToolRegistry.register(
        ToolDefinition(
            name="check_run_status",
            description="Get the current status of a specific stage run by run_id.",
            input_schema=CheckRunStatusInput,
            output_schema=CheckRunStatusOutput,
        ),
        execute,
    )


def _register_query_similar_use_cases():
    """Register tool to find similar use-cases by keyword matching."""

    async def execute(keywords: list[str], db: AsyncSession, limit: int = 3) -> QuerySimilarOutput:
        from sqlalchemy import or_, select

        from db.models import UseCase

        if not keywords:
            return QuerySimilarOutput(results=[])

        conditions = []
        for kw in keywords[:5]:  # limit to 5 keywords
            conditions.extend(
                [
                    UseCase.name.ilike(f"%{kw}%"),
                    UseCase.description.ilike(f"%{kw}%"),
                ]
            )

        result = await db.execute(select(UseCase).where(or_(*conditions)).limit(limit))
        use_cases = result.scalars().all()
        return QuerySimilarOutput(
            results=[
                {"use_case_id": uc.id, "name": uc.name, "description": uc.description or ""}
                for uc in use_cases
            ]
        )

    ToolRegistry.register(
        ToolDefinition(
            name="query_similar_use_cases",
            description="Find use-cases with similar names/descriptions using keyword matching.",
            input_schema=QuerySimilarInput,
            output_schema=QuerySimilarOutput,
        ),
        execute,
    )
