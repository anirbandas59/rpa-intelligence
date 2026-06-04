"""
Orchestrator — wires all Stage 2 agents together.
Handles three paths:
1. Document upload → extraction → scoring
2. Pasted text → extraction → scoring
3. Manual bands → scoring only

Supports dual agent paths (v1 legacy + v2 LangGraph) via feature flag.
"""

import hashlib
import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.complexity_agent import run_complexity_scoring
from agents.complexity_assessment import agent as complexity_assessment_agent
from agents.document_agent import process_document
from agents.process_agent import extract_bands_from_text
from config.settings import get_settings
from core.constants import ComplexityTier, RPATool
from core.exceptions import AgentExecutionError
from core.models.assessment import AssessmentResult
from core.models.scoring import AttributeBands, AttributeBandsWithSource, ScoringResult
from db.models import StageRun, UseCase

logger = logging.getLogger(__name__)


def compute_inputs_hash(inputs: dict) -> str:
    """Compute SHA256 hash of inputs for staleness detection."""
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


# ==================== ADAPTER FUNCTIONS ====================


def assessment_to_scoring_result(assessment: AssessmentResult) -> ScoringResult:
    """
    Convert AssessmentResult (v2) to ScoringResult (v1) for API compatibility.

    Used when LangGraph agent is enabled but frontend/API still expects
    the legacy ScoringResult format.

    Args:
        assessment: AssessmentResult from LangGraph agent

    Returns:
        ScoringResult in legacy format
    """
    # Map ComplexityTier enum to string
    complexity_class = assessment.complexity_tier.value

    # Rebuild attribute_weights dict from attribute_scores
    attribute_weights = {
        score.attribute_name.lower().replace(" ", "_"): score.weight
        for score in assessment.attribute_scores
    }

    # Derive effort from complexity tier (simplified — in future, use effort_table)
    effort_map = {
        "XS": (1, 1),
        "S": (2, 4),
        "M": (5, 5),
        "L": (6, 6),
        "XL": (8, 8),
    }
    effort_min_weeks, effort_max_weeks = effort_map.get(complexity_class, (0, 0))

    return ScoringResult(
        total_score=assessment.total_score,
        complexity_class=complexity_class,
        effort_min_weeks=effort_min_weeks,
        effort_max_weeks=effort_max_weeks,
        attribute_weights=attribute_weights,
    )


def _run_scoring_v1(bands: AttributeBands) -> ScoringResult:
    """
    V1 (legacy): Simple complexity_agent pipeline.

    Uses deterministic AttributeBands → ScoringResult pipeline.
    Zero LLM calls in scoring. Fast, simple, proven.

    Args:
        bands: AttributeBands with XS/S/M/L/XL values

    Returns:
        ScoringResult with all computed fields
    """
    logger.info("[V1] Running legacy complexity_agent pipeline")
    return run_complexity_scoring(bands)


def _run_scoring_v2(
    raw_attributes: dict[str, int],
    project_name: str = "RPA Process",
    rpa_tool: str = "unknown",
    session_id: str = "",
) -> AssessmentResult:
    """
    V2 (LangGraph): StateGraph complexity_assessment agent.

    Uses LangGraph StateGraph with isolated tools:
    - score_attributes node: raw counts → AttributeScore objects
    - classify_complexity node: deterministic classification + LLM reasoning

    State-managed, composable, observability built-in.

    Args:
        raw_attributes: Dict with activities, business_rules, layouts, interfaces, technology counts
        project_name: Project name for reporting
        rpa_tool: Detected RPA tool name
        session_id: Session ID for logging

    Returns:
        AssessmentResult with full assessment details
    """
    logger.info("[V2] Running LangGraph complexity_assessment agent")

    # Build process_analysis_state for agent input
    process_analysis_state = {
        "file_path": f"{project_name}.process",
        "session_id": session_id or "orchestrator",
        "raw_attributes": raw_attributes,
        "detected_rpa_tool": rpa_tool,
        "parsed_document": None,
        "sections": [],
        "entities": None,
        "status": "success",
        "warnings": [],
        "errors": [],
    }

    # Run LangGraph agent
    final_state = complexity_assessment_agent.run(
        process_analysis_state=process_analysis_state,
        session_id=session_id,
    )

    # Extract result
    if final_state.get("status") == "failed":
        errors = final_state.get("errors", [])
        raise AgentExecutionError(f"LangGraph agent failed: {errors}")

    assessment_result = final_state.get("assessment_result")
    if not assessment_result:
        raise AgentExecutionError("LangGraph agent produced no assessment_result")

    return assessment_result


async def run_s2_assessment(
    use_case_id: str,
    document_path: str | None,
    pasted_text: str | None,
    manual_bands: dict | None,
    session: AsyncSession,
    model: str = "claude-haiku-4-5",
) -> dict:
    """
    Run Stage 2 complexity assessment.
    Entry point for orchestrator.

    Args:
        use_case_id: UseCase ID
        document_path: Path to uploaded document (or None)
        pasted_text: User-pasted text (or None)
        manual_bands: Manual band entry dict (or None)
        session: Async DB session
        model: LLM model for extraction (default claude-haiku-4-5)

    Returns:
        Result dict with bands, scoring, and metadata

    Raises:
        DocumentProcessingError, LLMProviderError, AgentExecutionError
    """
    logger.info(f"Starting S2 assessment for use_case {use_case_id}")

    # Fetch use case
    result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise AgentExecutionError(f"UseCase {use_case_id} not found")

    # Determine path and extract bands
    bands_with_source: AttributeBandsWithSource | None = None

    if manual_bands:
        # Path 3: Manual bands (no LLM)
        logger.info("Using manual band entry (no LLM calls)")
        bands_with_source = AttributeBandsWithSource(**manual_bands)
        extraction_notes = "Manual entry by user"

    elif pasted_text:
        # Path 2: Pasted text → extraction
        logger.info("Extracting bands from pasted text")
        bands_with_source = await extract_bands_from_text(pasted_text, model=model)
        extraction_notes = "Extracted from pasted text"

    elif document_path:
        # Path 1: Document → text → extraction
        logger.info(f"Processing document: {document_path}")
        document_text = process_document(document_path)

        logger.info("Extracting bands from document text")
        bands_with_source = await extract_bands_from_text(document_text, model=model)
        extraction_notes = f"Extracted from {document_path}"

    else:
        raise AgentExecutionError("No input provided: must supply document_path, pasted_text, or manual_bands")

    # Convert to AttributeBands for scoring (drop source tags)
    bands = AttributeBands(
        activities=bands_with_source.activities,
        business_rules=bands_with_source.business_rules,
        layouts=bands_with_source.layouts,
        interfaces=bands_with_source.interfaces,
        technology=bands_with_source.technology,
    )

    # Feature flag: choose v1 (legacy) or v2 (LangGraph) agent
    settings = get_settings()
    use_langgraph = settings.use_langgraph_complexity_agent

    if use_langgraph:
        # V2: LangGraph StateGraph agent
        logger.info("Using LangGraph complexity_assessment agent (v2)")

        # Map bands to raw_attributes (band → midpoint of range)
        band_to_raw_map = {
            "XS": {"activities": 5, "business_rules": 0, "layouts": 0, "interfaces": 1, "technology": 0},
            "S": {"activities": 5, "business_rules": 1, "layouts": 1, "interfaces": 2, "technology": 0},
            "M": {"activities": 15, "business_rules": 2, "layouts": 2, "interfaces": 3, "technology": 1},
            "L": {"activities": 30, "business_rules": 3, "layouts": 5, "interfaces": 5, "technology": 2},
            "XL": {"activities": 45, "business_rules": 5, "layouts": 7, "interfaces": 7, "technology": 4},
        }

        raw_attributes = {
            "activities": band_to_raw_map.get(bands.activities, {}).get("activities", 0),
            "business_rules": band_to_raw_map.get(bands.business_rules, {}).get("business_rules", 0),
            "layouts": band_to_raw_map.get(bands.layouts, {}).get("layouts", 0),
            "interfaces": band_to_raw_map.get(bands.interfaces, {}).get("interfaces", 0),
            "technology": band_to_raw_map.get(bands.technology, {}).get("technology", 0),
        }

        project_name = use_case.name if use_case.name else f"UseCase-{use_case_id}"
        session_id = f"s2_run_{use_case_id}"

        # Run v2 agent
        assessment_result = _run_scoring_v2(
            raw_attributes=raw_attributes,
            project_name=project_name,
            rpa_tool="unknown",
            session_id=session_id,
        )

        # Convert to ScoringResult for API compatibility
        scoring_result = assessment_to_scoring_result(assessment_result)

        # Build result dict
        result_data = {
            "bands": bands_with_source.model_dump(),
            "scoring": scoring_result.model_dump(),
            "extraction_notes": extraction_notes,
            "model_used": model if (pasted_text or document_path) else None,
            # Store full assessment for future use
            "_assessment_result": {
                "complexity_tier": assessment_result.complexity_tier.value,
                "confidence_score": assessment_result.confidence_score,
                "reasoning": assessment_result.reasoning,
                "requires_tech_lead_review": assessment_result.requires_tech_lead_review,
            },
        }
    else:
        # V1: Legacy complexity_agent pipeline
        logger.info("Using legacy complexity_agent (v1)")
        scoring_result = _run_scoring_v1(bands)

        # Build result dict
        result_data = {
            "bands": bands_with_source.model_dump(),
            "scoring": scoring_result.model_dump(),
            "extraction_notes": extraction_notes,
            "model_used": model if (pasted_text or document_path) else None,
        }

    logger.info(f"S2 assessment complete: {scoring_result.complexity_class} class, {scoring_result.total_score} score")

    return result_data


async def create_s2_run(
    use_case_id: str,
    inputs_snapshot: dict,
    session: AsyncSession,
) -> StageRun:
    """
    Create a StageRun record for S2 with status='running'.
    Returns the created StageRun.

    Args:
        use_case_id: UseCase ID
        inputs_snapshot: Snapshot of current s2_inputs
        session: Async DB session

    Returns:
        Created StageRun record
    """
    # Count existing S2 runs for this use case
    count_result = await session.execute(
        select(StageRun).where(StageRun.use_case_id == use_case_id, StageRun.stage == "s2")
    )
    run_number = len(count_result.scalars().all()) + 1

    inputs_hash = compute_inputs_hash(inputs_snapshot)

    stage_run = StageRun(
        use_case_id=use_case_id,
        stage="s2",
        run_number=run_number,
        inputs_snapshot=inputs_snapshot,
        inputs_hash=inputs_hash,
        result={},
        status="running",
        model_used=None,
    )

    session.add(stage_run)
    await session.commit()
    await session.refresh(stage_run)

    logger.info(f"Created S2 StageRun {stage_run.id} (run #{run_number}) for use_case {use_case_id}")
    return stage_run


async def finalize_s2_run(
    run_id: str,
    result_data: dict,
    model_used: str | None,
    session: AsyncSession,
) -> None:
    """
    Update StageRun with result and mark status='complete'.

    Args:
        run_id: StageRun ID
        result_data: Result dict from orchestrator
        model_used: Model name used for extraction (or None)
        session: Async DB session
    """
    result = await session.execute(select(StageRun).where(StageRun.id == run_id))
    stage_run = result.scalar_one_or_none()

    if not stage_run:
        raise AgentExecutionError(f"StageRun {run_id} not found")

    stage_run.result = result_data
    stage_run.model_used = model_used
    stage_run.status = "complete"

    # Update use_case.s2_latest_run_id
    uc_result = await session.execute(select(UseCase).where(UseCase.id == stage_run.use_case_id))
    use_case = uc_result.scalar_one_or_none()
    if use_case:
        use_case.s2_latest_run_id = run_id
        use_case.updated_at = datetime.utcnow()

    await session.commit()
    logger.info(f"Finalized S2 StageRun {run_id} as complete")


async def fail_s2_run(
    run_id: str,
    error_message: str,
    session: AsyncSession,
) -> None:
    """
    Mark StageRun as failed with error message.

    Args:
        run_id: StageRun ID
        error_message: Error description
        session: Async DB session
    """
    result = await session.execute(select(StageRun).where(StageRun.id == run_id))
    stage_run = result.scalar_one_or_none()

    if stage_run:
        stage_run.status = "failed"
        stage_run.error_message = error_message
        await session.commit()
        logger.error(f"Failed S2 StageRun {run_id}: {error_message}")
