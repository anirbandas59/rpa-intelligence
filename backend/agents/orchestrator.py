"""
Orchestrator — wires all Stage 2 agents together.
Handles three paths:
1. Document upload → extraction → scoring
2. Pasted text → extraction → scoring
3. Manual bands → scoring only
"""

import logging
import hashlib
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import UseCase, StageRun
from core.models.scoring import AttributeBands, AttributeBandsWithSource, ScoringResult
from agents.document_agent import process_document
from agents.process_agent import extract_bands_from_text
from agents.complexity_agent import run_complexity_scoring
from core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)


def compute_inputs_hash(inputs: dict) -> str:
    """Compute SHA256 hash of inputs for staleness detection."""
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


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

    # Run deterministic scoring
    logger.info("Running deterministic complexity scoring")
    scoring_result: ScoringResult = run_complexity_scoring(bands)

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
