"""
Stage 2 (Complexity Assessment) API routes for RPA Intelligence Platform.

Provides endpoints for managing complexity assessment workflow through three input paths:
document upload (PDF/DOCX), pasted text, or manual band entry. AI extraction uses Haiku
for band-level classification, then deterministic scoring maps bands to complexity class.

Key endpoints:
- POST /{id}/s2/documents: Upload PDF/DOCX for AI extraction
- POST /{id}/s2/text: Save pasted text for AI extraction
- PATCH /{id}/s2/inputs: Update manual band values or correct AI extractions
- POST /{id}/s2/runs: Create assessment run (async, auto-selects latest input)
- GET /{id}/s2/runs: List all runs
- GET /{id}/s2/runs/{run_id}: Get single run with full details

Complexity flow:
1. User provides input via document upload, pasted text, or manual bands
2. User triggers run via POST /runs (timestamp-aware selection picks latest input)
3. Backend runs document_agent (Haiku) → process_agent (extraction + reflexion)
   → complexity_agent (deterministic scoring)
4. Result includes: band assignments, total_score (7-28),
   complexity_class (XS/S/M/L/XL), effort range
5. User can edit extracted bands via PATCH /inputs and re-run
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import (
    create_s2_run as _orchestrator_create_s2_run,
)
from agents.orchestrator import (
    fail_s2_run,
    finalize_s2_run,
    run_s2_assessment,
)
from api.dependencies import get_current_user, get_db, get_session_maker
from core.exceptions import AgentExecutionError, DocumentProcessingError, LLMProviderError
from db.models import StageRun, UploadedFile, UseCase, User

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# Request/Response models
class PatchS2InputsRequest(BaseModel):
    """Request to update S2 inputs (manual bands or text)."""

    pasted_text: str | None = None
    activities: str | None = None
    activities_source: str | None = None
    business_rules: str | None = None
    business_rules_source: str | None = None
    layouts: str | None = None
    layouts_source: str | None = None
    interfaces: str | None = None
    interfaces_source: str | None = None
    technology: str | None = None
    technology_source: str | None = None


class CreateS2RunRequest(BaseModel):
    """Request to create S2 run."""

    model: str = "claude-haiku-4-5"


class S2RunResponse(BaseModel):
    """Response for S2 run creation."""

    run_id: str
    status: str
    message: str


# Background task for S2 run
async def _execute_s2_background_task(
    run_id: str,
    use_case_id: str,
    document_path: str | None,
    pasted_text: str | None,
    manual_bands: dict[str, str] | None,
    model: str,
    db_factory,
):
    """
    Execute Stage 2 complexity assessment in background with independent database session.

    Runs orchestrator workflow: document_agent (if document/text) → process_agent
    (extraction + reflexion) → complexity_agent (deterministic scoring). Updates
    StageRun status to "complete" or "failed" based on outcome.

    Args:
        run_id: StageRun ID to update
        use_case_id: UseCase ID being assessed
        document_path: Path to uploaded document (mutually exclusive with others)
        pasted_text: Pasted process description (mutually exclusive with others)
        manual_bands: Manual band dict (mutually exclusive with others)
        model: LLM model name for extraction (if document/text provided)
        db_factory: Async session factory for independent database session

    Flow:
    - Calls run_s2_assessment from orchestrator
    - On success: calls finalize_s2_run (sets status="complete")
    - On error: calls fail_s2_run (sets status="failed" with error message)
    """
    async with db_factory() as session:
        try:
            result_data = await run_s2_assessment(
                use_case_id=use_case_id,
                document_path=document_path,
                pasted_text=pasted_text,
                manual_bands=manual_bands,
                session=session,
                model=model,
            )

            model_used = result_data.get("model_used")
            await finalize_s2_run(run_id, result_data, model_used, session)

        except (DocumentProcessingError, LLMProviderError, AgentExecutionError) as e:
            await fail_s2_run(run_id, str(e), session)
        except Exception as e:
            logger.exception(f"Unexpected error in S2 run {run_id}")
            await fail_s2_run(run_id, f"Unexpected error: {e}", session)


@router.post("/{id}/s2/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload PDF or DOCX document for Stage 2 complexity extraction.

    Saves file to uploads/ directory and creates UploadedFile database record.
    File is ready for processing when user creates S2 run. Only .pdf and .docx
    formats are supported.

    Args:
        id: UseCase ID to upload document for
        file: Uploaded file from multipart form data
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with file_id, stored_path, original_filename, size_bytes

    Raises:
        HTTPException: 404 if use case not found, 400 if unsupported file type,
                      500 if file save fails
    """
    # Verify use case exists
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Validate file type (only PDF and DOCX supported by document_agent)
    filename = file.filename or "document"
    suffix = Path(filename).suffix.lower()
    if suffix not in [".docx", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported")

    # Generate unique filename to avoid collisions
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}{suffix}"
    stored_path = UPLOAD_DIR / stored_filename

    # Save file to disk
    try:
        content = await file.read()
        with open(stored_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.exception(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Record in DB
    uploaded_file = UploadedFile(
        id=file_id,
        use_case_id=id,
        stage="s2",
        original_filename=filename,
        stored_path=str(stored_path),
        file_type=suffix,
        size_bytes=len(content),
        uploaded_by=current_user.id,
    )

    db.add(uploaded_file)
    await db.commit()
    await db.refresh(uploaded_file)

    logger.info(f"Uploaded file {file_id} for use_case {id}: {stored_path}")

    return {
        "file_id": file_id,
        "stored_path": str(stored_path),
        "original_filename": filename,
        "size_bytes": len(content),
    }


@router.post("/{id}/s2/text", status_code=status.HTTP_200_OK)
async def save_pasted_text(
    id: str,
    request: PatchS2InputsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save pasted process description to s2_inputs for AI extraction.

    Alternative to document upload when user has process description as text.
    Text is processed by document_agent → process_agent workflow same as uploaded files.

    Args:
        id: UseCase ID to save text for
        request: Must contain pasted_text field
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Updated s2_inputs dict with pasted_text, source tag, and timestamp

    Raises:
        HTTPException: 404 if use case not found, 400 if pasted_text missing
    """
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    if not request.pasted_text:
        raise HTTPException(status_code=400, detail="pasted_text is required")

    use_case.s2_inputs = {
        **use_case.s2_inputs,
        "pasted_text": request.pasted_text,
        "pasted_text_source": "manual",
        "pasted_text_updated_at": datetime.utcnow().isoformat(),
    }
    use_case.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(use_case)

    return {"s2_inputs": use_case.s2_inputs}


@router.patch("/{id}/s2/inputs", status_code=status.HTTP_200_OK)
async def update_s2_inputs(
    id: str,
    request: PatchS2InputsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update attribute band values and source tags on s2_inputs (manual or corrected).

    Used for manual band entry when user knows bands upfront, or for correcting
    AI-extracted bands after reviewing extraction results. Source tags are automatically
    set to "manual" unless explicitly provided.

    Args:
        id: UseCase ID to update bands for
        request: Partial update with any of 5 band fields and optional source tags
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Updated s2_inputs dict with new bands and manual_bands_updated_at timestamp

    Raises:
        HTTPException: 404 if use case not found
    """
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Update only provided fields (partial update pattern)
    updates = {}
    if request.activities is not None:
        updates["activities"] = request.activities
        updates["activities_source"] = request.activities_source or "manual"
    if request.business_rules is not None:
        updates["business_rules"] = request.business_rules
        updates["business_rules_source"] = request.business_rules_source or "manual"
    if request.layouts is not None:
        updates["layouts"] = request.layouts
        updates["layouts_source"] = request.layouts_source or "manual"
    if request.interfaces is not None:
        updates["interfaces"] = request.interfaces
        updates["interfaces_source"] = request.interfaces_source or "manual"
    if request.technology is not None:
        updates["technology"] = request.technology
        updates["technology_source"] = request.technology_source or "manual"
    if request.pasted_text is not None:
        updates["pasted_text"] = request.pasted_text

    # Add timestamp when any manual band is updated (used for input selection priority)
    if any(
        [
            request.activities,
            request.business_rules,
            request.layouts,
            request.interfaces,
            request.technology,
        ]
    ):
        updates["manual_bands_updated_at"] = datetime.utcnow().isoformat()

    use_case.s2_inputs = {**use_case.s2_inputs, **updates}
    use_case.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(use_case)

    return {"s2_inputs": use_case.s2_inputs}


@router.post("/{id}/s2/runs", status_code=status.HTTP_202_ACCEPTED, response_model=S2RunResponse)
async def create_s2_run(
    id: str,
    request: CreateS2RunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    db_factory=Depends(get_session_maker),
):
    """
    Create Stage 2 complexity assessment run with timestamp-aware input selection.

    Returns immediately with run_id and status="running". Processing happens in background.
    Automatically selects latest input based on timestamps (most recent wins):
    document (created_at) vs pasted_text (updated_at) vs manual_bands (updated_at).

    Three input paths:
    1. Document upload: Uses latest UploadedFile.stored_path (requires document_agent + process_agent)
    2. Pasted text: Uses s2_inputs.pasted_text (requires document_agent + process_agent)
    3. Manual bands: Uses all 5 bands from s2_inputs (skips extraction, runs complexity_agent only)

    Args:
        id: UseCase ID to assess
        request: Model selection for AI extraction (default: claude-haiku-4-5)
        background_tasks: FastAPI background task scheduler (injected)
        db: Database session (injected)
        current_user: Authenticated user (injected)
        db_factory: Session factory for background task's independent session (injected)

    Returns:
        S2RunResponse with run_id and status="running"

    Raises:
        HTTPException: 404 if use case not found, 400 if no valid input provided
    """
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Gather all inputs WITH timestamps
    s2_inputs = use_case.s2_inputs or {}

    # Check for document
    file_result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.use_case_id == id, UploadedFile.stage == "s2")
        .order_by(UploadedFile.created_at.desc())
    )
    latest_file = file_result.scalars().first()
    document_path = latest_file.stored_path if latest_file else None
    document_created_at = latest_file.created_at if latest_file else None

    # Check for pasted text
    pasted_text = s2_inputs.get("pasted_text") if s2_inputs.get("pasted_text") else None
    pasted_text_updated_at = s2_inputs.get("pasted_text_updated_at")

    # Check for manual bands (all five present)
    required_bands = ["activities", "business_rules", "layouts", "interfaces", "technology"]
    manual_bands = None
    manual_bands_updated_at = None
    if all(band in s2_inputs for band in required_bands):
        manual_bands = {
            "activities": s2_inputs["activities"],
            "activities_source": s2_inputs.get("activities_source", "manual"),
            "business_rules": s2_inputs["business_rules"],
            "business_rules_source": s2_inputs.get("business_rules_source", "manual"),
            "layouts": s2_inputs["layouts"],
            "layouts_source": s2_inputs.get("layouts_source", "manual"),
            "interfaces": s2_inputs["interfaces"],
            "interfaces_source": s2_inputs.get("interfaces_source", "manual"),
            "technology": s2_inputs["technology"],
            "technology_source": s2_inputs.get("technology_source", "manual"),
        }
        manual_bands_updated_at = s2_inputs.get("manual_bands_updated_at")

    # Use timestamp-aware selection to pick the most recent input (orchestrator helper)
    from agents.orchestrator import _select_latest_input

    try:
        source_type, input_data, selected_bands = _select_latest_input(
            document_path,
            document_created_at,
            pasted_text,
            pasted_text_updated_at,
            manual_bands,
            manual_bands_updated_at,
        )

        # Map selected input to background task params (only one will be non-None)
        if source_type == "document":
            document_path = input_data
            pasted_text = None
            manual_bands = None
        elif source_type == "text":
            pasted_text = input_data
            document_path = None
            manual_bands = None
        else:  # manual
            manual_bands = selected_bands
            document_path = None
            pasted_text = None

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"No valid input provided: {str(e)}",
        )

    # Create StageRun record with inputs snapshot (hash used for staleness detection)
    inputs_snapshot = dict(use_case.s2_inputs or {})
    stage_run = await _orchestrator_create_s2_run(id, inputs_snapshot, db)

    # Fire background task
    background_tasks.add_task(
        _execute_s2_background_task,
        run_id=stage_run.id,
        use_case_id=id,
        document_path=document_path,
        pasted_text=pasted_text,
        manual_bands=manual_bands,
        model=request.model,
        db_factory=db_factory,
    )

    return S2RunResponse(
        run_id=stage_run.id,
        status="running",
        message="S2 assessment started in background",
    )


@router.get("/{id}/s2/runs", status_code=status.HTTP_200_OK)
async def list_s2_runs(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all Stage 2 complexity assessment runs for a use case (most recent first).

    Returns summary view including status, timestamps, complexity class, and error messages.
    Useful for version history and comparing results across runs.

    Args:
        id: UseCase ID to list runs for
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dict with "runs" list containing run summaries
    """
    result = await db.execute(
        select(StageRun)
        .where(StageRun.use_case_id == id, StageRun.stage == "s2")
        .order_by(StageRun.created_at.desc())
        .execution_options(populate_existing=True)  # Force fresh data from DB
    )
    runs = result.scalars().all()

    return {
        "runs": [
            {
                "id": run.id,
                "run_number": run.run_number,
                "status": run.status,
                "created_at": run.created_at.isoformat(),
                "model_used": run.model_used,
                "error_message": run.error_message,
                "result": run.result if run.status == "complete" else None,
            }
            for run in runs
        ]
    }


@router.get("/{id}/s2/runs/{run_id}", status_code=status.HTTP_200_OK)
async def get_s2_run(
    id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get single Stage 2 run with full details (inputs snapshot, result, hash).

    Returns complete run record for detailed inspection, version comparison, or debugging.
    Includes inputs_hash for staleness detection and full result with band assignments,
    complexity class, total score, and effort estimates.

    Args:
        id: UseCase ID owning the run
        run_id: StageRun ID to retrieve
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Full StageRun record with all fields

    Raises:
        HTTPException: 404 if run not found or doesn't belong to this use case
    """
    result = await db.execute(
        select(StageRun).where(
            StageRun.id == run_id, StageRun.use_case_id == id, StageRun.stage == "s2"
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="StageRun not found")

    return {
        "id": run.id,
        "run_number": run.run_number,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "model_used": run.model_used,
        "inputs_snapshot": run.inputs_snapshot,
        "inputs_hash": run.inputs_hash,
        "result": run.result,
        "error_message": run.error_message,
    }
