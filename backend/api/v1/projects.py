import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from core.exceptions import DocumentProcessingError
from core.scoring.weight_matrix import load_weight_matrix
from db.models import PhaseConfig, Project, UploadSession, UseCase, User, WeightConfig
from db.session import AsyncSessionLocal
from services.file_storage_service import file_storage_service
from services.timeline_service import DEFAULT_BUFFERS

router = APIRouter()
logger = logging.getLogger(__name__)


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime


class UseCaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    source_platform: str | None
    install_status: str | None
    s1_latest_run_id: str | None = None
    s2_latest_run_id: str | None = None
    s3_latest_run_id: str | None = None
    s4_latest_run_id: str | None = None
    created_at: datetime


class WeightConfigRequest(BaseModel):
    """Request to update weight config for a project."""

    config: dict[str, dict[str, int]]  # Weight matrix override
    yes_threshold: int = 50


class WeightConfigResponse(BaseModel):
    """Response for weight config."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    is_active: bool
    config: dict
    yes_threshold: int
    created_at: datetime


class PhaseConfigRequest(BaseModel):
    """Request to update phase buffer configuration."""

    config: dict[str, int]  # Buffer overrides: {"define": 2, "design": {"S": 1, "M": 2, ...}, ...}
    sprint_length_weeks: int = 2


class PhaseConfigResponse(BaseModel):
    """Response for phase config."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    is_active: bool
    config: dict
    sprint_length_weeks: int
    created_at: datetime


class BulkUploadResponse(BaseModel):
    """Response for bulk upload with session ID and preview."""

    upload_id: str
    filename: str
    columns: list[str]
    preview: list[dict[str, str]]
    row_count: int


class ColumnMapping(BaseModel):
    """Maps CSV/XLSX columns to UseCase fields."""

    name: str  # required — maps to UseCase.name
    description: str | None = None
    source_platform: str | None = None
    install_status: str | None = None


class UpdateMappingRequest(BaseModel):
    """Request to update column mapping for upload session."""

    column_mapping: ColumnMapping
    edited_rows: list[dict[str, str]] | None = None  # Optional inline edits


class BulkConfirmResponse(BaseModel):
    """Response after bulk upload confirmation."""

    upload_id: str
    status: str  # "processing"
    job_id: str


class BulkUploadStatusResponse(BaseModel):
    """Progress status for bulk upload processing."""

    upload_id: str
    status: str  # "preview" | "confirmed" | "processing" | "complete" | "failed"
    created_count: int | None
    assessed_count: int | None
    total_count: int
    error: str | None


@router.post("", response_model=ProjectResponse)
async def create_project(
    req: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(name=req.name, description=req.description, created_by=user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects.

    Superusers see all projects. Regular users see only their own projects.

    Args:
        user: Current authenticated user (injected)
        db: Database session (injected)

    Returns:
        List of projects accessible to the current user
    """
    # Superuser sees all, regular user sees only their own
    if user.role == "superuser":
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    else:
        result = await db.execute(
            select(Project)
            .where(Project.created_by == user.id)
            .order_by(Project.created_at.desc())
        )
    return result.scalars().all()


@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a project and all associated use cases (cascade).

    Only the project owner can delete their project, unless the user is a superuser.
    Superusers can delete any project.

    Args:
        id: Project ID to delete
        user: Current authenticated user (injected)
        db: Database session (injected)

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 404 if project not found or user doesn't have access
    """
    # Check ownership - superuser can delete any project, regular user only their own
    result = await db.execute(
        select(Project).where(
            Project.id == id,
            (Project.created_by == user.id) | (user.role == "superuser"),
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or you don't have permission to delete it",
        )

    # Cascade delete handled by SQLAlchemy (UseCase.project_id has ondelete="CASCADE")
    await db.delete(project)
    await db.commit()

    logger.info(f"Deleted project {id} by user {user.id} (role: {user.role})")


@router.get("/{id}/use-cases", response_model=list[UseCaseListItem])
async def list_project_use_cases(
    id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all use cases for a project."""
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch use cases
    use_cases_result = await db.execute(
        select(UseCase).where(UseCase.project_id == id).order_by(UseCase.created_at.desc())
    )
    return use_cases_result.scalars().all()


@router.get("/{id}/weights", status_code=status.HTTP_200_OK)
async def get_project_weights(
    id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get active WeightConfig for project.
    If none exists, returns default weight matrix.

    Returns:
        WeightConfig or default weights
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch active weight config
    config_result = await db.execute(
        select(WeightConfig).where(WeightConfig.project_id == id, WeightConfig.is_active)
    )
    weight_config = config_result.scalars().first()

    if weight_config:
        return {
            "id": weight_config.id,
            "project_id": weight_config.project_id,
            "name": weight_config.name,
            "is_active": weight_config.is_active,
            "config": weight_config.config,
            "yes_threshold": weight_config.yes_threshold,
            "created_at": weight_config.created_at.isoformat(),
            "source": "project_override",
        }
    else:
        # Return default matrix
        default_matrix = load_weight_matrix()
        return {
            "id": None,
            "project_id": id,
            "name": "default",
            "is_active": True,
            "config": default_matrix,
            "yes_threshold": 50,
            "created_at": None,
            "source": "default",
        }


@router.put("/{id}/weights", status_code=status.HTTP_200_OK)
async def update_project_weights(
    id: str,
    request: WeightConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update (or create) WeightConfig for project.
    Deactivates any existing active config and creates a new one.

    Returns:
        Created WeightConfig
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Deactivate existing active configs
    existing_result = await db.execute(
        select(WeightConfig).where(WeightConfig.project_id == id, WeightConfig.is_active)
    )
    existing_configs = existing_result.scalars().all()
    for config in existing_configs:
        config.is_active = False

    # Create new config
    new_config = WeightConfig(
        project_id=id,
        name="custom",
        is_active=True,
        config=request.config,
        yes_threshold=request.yes_threshold,
        created_by=user.id,
    )

    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    return {
        "id": new_config.id,
        "project_id": new_config.project_id,
        "name": new_config.name,
        "is_active": new_config.is_active,
        "config": new_config.config,
        "yes_threshold": new_config.yes_threshold,
        "created_at": new_config.created_at.isoformat(),
    }


@router.get("/{id}/phases", status_code=status.HTTP_200_OK)
async def get_project_phase_config(
    id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get active PhaseConfig for project.
    If none exists, returns default buffer configuration.

    Returns:
        PhaseConfig or default phase buffers
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch active phase config
    config_result = await db.execute(
        select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active)
    )
    phase_config = config_result.scalars().first()

    if phase_config:
        return {
            "id": phase_config.id,
            "project_id": phase_config.project_id,
            "is_active": phase_config.is_active,
            "config": phase_config.config,
            "sprint_length_weeks": phase_config.sprint_length_weeks,
            "created_at": phase_config.created_at.isoformat(),
            "source": "project_override",
        }
    else:
        # Return default buffers
        return {
            "id": None,
            "project_id": id,
            "is_active": True,
            "config": DEFAULT_BUFFERS,
            "sprint_length_weeks": 2,
            "created_at": None,
            "source": "default",
        }


@router.put("/{id}/phases", status_code=status.HTTP_200_OK)
async def update_project_phase_config(
    id: str,
    request: PhaseConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update (or create) PhaseConfig for project.
    Deactivates any existing active config and creates a new one.

    Returns:
        Created PhaseConfig
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Deactivate existing active configs
    existing_result = await db.execute(
        select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active)
    )
    existing_configs = existing_result.scalars().all()
    for config in existing_configs:
        config.is_active = False

    # Create new config
    new_config = PhaseConfig(
        project_id=id,
        is_active=True,
        config=request.config,
        sprint_length_weeks=request.sprint_length_weeks,
    )

    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    return {
        "id": new_config.id,
        "project_id": new_config.project_id,
        "is_active": new_config.is_active,
        "config": new_config.config,
        "sprint_length_weeks": new_config.sprint_length_weeks,
        "created_at": new_config.created_at.isoformat(),
    }


@router.post("/{id}/use-cases/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_use_cases(
    id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Upload file and create upload session.

    Returns upload_id, columns, preview (first 5 rows), and total row count.
    File is stored server-side for later processing.
    """
    # Verify project exists and belongs to current user
    result = await db.execute(
        select(Project).where(Project.id == id, Project.created_by == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found or you don't have access to it"
        )

    # Read file content
    content = await file.read()
    if not content:
        raise DocumentProcessingError("File is empty")

    if not file.filename:
        raise DocumentProcessingError("Filename is missing")

    # Create upload session and store file
    session = file_storage_service.create_upload_session(
        file_content=content,
        filename=file.filename,
        project_id=id,
        user_id=current_user.id,
    )

    # Get preview rows
    preview = file_storage_service.get_preview_rows(session, limit=5)

    # Save session to database
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return BulkUploadResponse(
        upload_id=session.id,
        filename=session.filename,
        columns=session.columns["columns"],
        preview=preview,
        row_count=session.row_count,
    )


@router.put("/use-cases/bulk-upload/{upload_id}/mapping", response_model=BulkUploadResponse)
async def update_column_mapping(
    upload_id: str,
    request: UpdateMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Store column mapping for upload session.

    Validates mapping and optionally updates preview with mapped columns.
    """
    # Get session
    session = await db.get(UploadSession, upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")

    # Verify user ownership
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate status
    if session.status != "preview":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update mapping: upload is already {session.status}"
        )

    # Validate column mapping against session columns
    columns = session.columns["columns"]
    if request.column_mapping.name not in columns:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.column_mapping.name}' not found in file"
        )

    # Store mapping
    session.column_mapping = request.column_mapping.model_dump()
    session.status = "confirmed"
    await db.commit()

    # Return updated preview
    preview = file_storage_service.get_preview_rows(session, limit=5)

    return BulkUploadResponse(
        upload_id=session.id,
        filename=session.filename,
        columns=columns,
        preview=preview,
        row_count=session.row_count,
    )


@router.post("/use-cases/bulk-upload/{upload_id}/confirm", response_model=BulkConfirmResponse)
async def confirm_bulk_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 3: Confirm creation and trigger background processing.

    Creates use cases in batches and triggers Stage 1 assessment for each.
    Returns immediately with job ID for progress polling.
    """
    # Get session
    session = await db.get(UploadSession, upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")

    # Verify user ownership
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate state
    if session.column_mapping is None:
        raise HTTPException(status_code=400, detail="Column mapping not set")

    if session.status not in ["preview", "confirmed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Upload already {session.status}"
        )

    # Update status
    session.status = "processing"
    await db.commit()

    # Add background task
    background_tasks.add_task(
        process_bulk_upload,
        upload_id=upload_id,
    )

    return BulkConfirmResponse(
        upload_id=upload_id,
        status="processing",
        job_id=upload_id,
    )


@router.get("/use-cases/bulk-upload/{upload_id}/status", response_model=BulkUploadStatusResponse)
async def get_bulk_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Poll endpoint for upload progress.

    Returns creation progress and Stage 1 assessment progress.
    """
    # Get session
    session = await db.get(UploadSession, upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")

    # Verify user ownership
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Count assessed use cases
    assessed_count = 0
    if session.use_case_ids and session.use_case_ids.get("ids"):
        use_case_id_list = session.use_case_ids["ids"]
        result = await db.execute(
            select(func.count(UseCase.id))
            .where(UseCase.id.in_(use_case_id_list))
            .where(UseCase.s1_latest_run_id.isnot(None))
        )
        assessed_count = result.scalar() or 0

    return BulkUploadStatusResponse(
        upload_id=session.id,
        status=session.status,
        created_count=session.created_count,
        assessed_count=assessed_count,
        total_count=session.row_count,
        error=session.error,
    )


async def process_bulk_upload(upload_id: str):
    """
    Background task for processing bulk upload.

    Creates use cases in batches and triggers Stage 1 assessments.
    Updates session status to 'complete' or 'failed'.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get session
            session = await db.get(UploadSession, upload_id)
            if not session:
                logger.error(f"Upload session not found: {upload_id}")
                return

            if not session.column_mapping:
                session.status = "failed"
                session.error = "Column mapping not set"
                await db.commit()
                return

            # Parse column mapping
            column_mapping = session.column_mapping

            # Process file in batches
            use_case_ids = []
            batch_count = 0

            async for batch in file_storage_service.parse_file_with_mapping(
                session=session,
                column_mapping=column_mapping,
                batch_size=1000,
            ):
                # Add batch to database
                db.add_all(batch)
                await db.commit()

                # Refresh to get IDs
                for uc in batch:
                    await db.refresh(uc)
                    use_case_ids.append(uc.id)

                batch_count += 1
                logger.info(
                    f"Processed batch {batch_count} for upload {upload_id}: "
                    f"{len(batch)} use cases"
                )

            # Update session status
            session.status = "complete"
            session.created_count = len(use_case_ids)
            session.use_case_ids = {"ids": use_case_ids}
            await db.commit()

            logger.info(
                f"Bulk upload {upload_id} complete: {len(use_case_ids)} use cases created"
            )

            # TODO: Trigger Stage 1 assessments via queue
            # This will be implemented when stage1_queue_service is added
            # For now, use cases are created but assessments must be triggered manually

        except Exception as e:
            logger.exception(f"Bulk upload {upload_id} failed")
            async with AsyncSessionLocal() as db_error:
                session = await db_error.get(UploadSession, upload_id)
                if session:
                    session.status = "failed"
                    session.error = str(e)
                    await db_error.commit()
