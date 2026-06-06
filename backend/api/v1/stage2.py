"""
Stage 2 (Complexity) API routes.
Document upload → AI extraction → deterministic scoring.
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
    Background task to execute S2 assessment.
    Updates StageRun on completion or failure.
    db_factory is injected via Depends(get_session_maker) so tests can override it.
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
    Upload a document for S2 processing.
    Saves file to uploads/ and records UploadedFile.

    Returns:
        file_id: ID of created UploadedFile record
        stored_path: Path where file was stored
    """
    # Verify use case exists
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Validate file type
    filename = file.filename or "document"
    suffix = Path(filename).suffix.lower()
    if suffix not in [".docx", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported")

    # Generate unique filename
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}{suffix}"
    stored_path = UPLOAD_DIR / stored_filename

    # Save file
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
    Save pasted text to s2_inputs.

    Returns:
        Updated s2_inputs
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
    Update band values and source tags on s2_inputs.
    Used for manual band entry or correcting AI-extracted values.

    Returns:
        Updated s2_inputs
    """
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    # Update only provided fields
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

    # Add timestamp when any manual band is updated
    if any([
        request.activities,
        request.business_rules,
        request.layouts,
        request.interfaces,
        request.technology,
    ]):
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
    Create S2 run. Returns immediately with run_id and status='running'.
    Processing happens in background.

    Three input paths:
    1. Document upload: reads latest UploadedFile for s2
    2. Pasted text: reads s2_inputs.pasted_text
    3. Manual bands: reads s2_inputs.activities/business_rules/etc
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

    # Use timestamp-aware selection to pick the most recent input
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

        # Map to background task params (only one will be non-None)
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

    # Create StageRun record — use s2_inputs as snapshot so staleness hash matches readiness check
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
    List all S2 StageRuns for a use case.

    Returns:
        List of StageRun records
    """
    result = await db.execute(
        select(StageRun)
        .where(StageRun.use_case_id == id, StageRun.stage == "s2")
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
    Get single S2 StageRun with full inputs_snapshot + result.

    Returns:
        StageRun record
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
