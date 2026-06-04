import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from core.exceptions import DocumentProcessingError
from core.scoring.weight_matrix import load_weight_matrix
from db.models import PhaseConfig, Project, UseCase, User, WeightConfig
from services.timeline_service import DEFAULT_BUFFERS

try:
    import openpyxl
except ImportError:
    openpyxl = None

router = APIRouter()


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
    """Response for bulk upload preview."""

    columns: list[str]
    preview: list[dict[str, str]]
    row_count: int


class ColumnMapping(BaseModel):
    """Maps CSV/XLSX columns to UseCase fields."""

    name: str  # required — maps to UseCase.name
    description: str | None = None
    source_platform: str | None = None
    install_status: str | None = None


class BulkConfirmRequest(BaseModel):
    """Request to confirm and create use cases from bulk upload."""

    column_mapping: ColumnMapping  # maps CSV column names → UseCase field names
    rows: list[dict[str, str]]  # the actual data rows (from the preview)


class BulkConfirmResponse(BaseModel):
    """Response after bulk confirmation."""

    created: int
    use_case_ids: list[str]


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
    result = await db.execute(select(Project))
    return result.scalars().all()


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
    config_result = await db.execute(select(WeightConfig).where(WeightConfig.project_id == id, WeightConfig.is_active))
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
    config_result = await db.execute(select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active))
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
    existing_result = await db.execute(select(PhaseConfig).where(PhaseConfig.project_id == id, PhaseConfig.is_active))
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
    Upload and preview a CSV or XLSX file for bulk use-case creation.
    Returns column names, first 5 data rows, and total row count.
    """
    # Verify project exists and belongs to current user
    result = await db.execute(select(Project).where(Project.id == id, Project.created_by == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Read file content
    content = await file.read()
    if not content:
        raise DocumentProcessingError("File is empty")

    columns = []
    preview = []
    row_count = 0

    try:
        if file.filename.endswith(".csv"):
            # Parse CSV
            text_content = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text_content))
            if not reader.fieldnames:
                raise DocumentProcessingError("CSV has no columns")
            columns = list(reader.fieldnames)
            for i, row in enumerate(reader):
                if i < 5:
                    preview.append(dict(row))
                row_count += 1
        elif file.filename.endswith(".xlsx"):
            # Parse XLSX
            if openpyxl is None:
                raise DocumentProcessingError("openpyxl is not installed")
            workbook = openpyxl.load_workbook(io.BytesIO(content))
            ws = workbook.active
            # Get columns from first row
            for cell in ws[1]:
                if cell.value:
                    columns.append(str(cell.value))
            # Get data rows
            for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                if i < 5:
                    row_dict = {columns[j]: str(val) if val is not None else "" for j, val in enumerate(row) if j < len(columns)}
                    preview.append(row_dict)
                row_count += 1
        else:
            raise DocumentProcessingError(f"Unsupported file type: {file.filename}. Only .csv and .xlsx are supported.")
    except DocumentProcessingError:
        raise
    except UnicodeDecodeError:
        raise DocumentProcessingError("File encoding error. Please ensure the file is UTF-8 encoded.")
    except Exception as e:
        raise DocumentProcessingError(f"Failed to parse file: {str(e)}")

    return BulkUploadResponse(columns=columns, preview=preview, row_count=row_count)


@router.post("/{id}/use-cases/bulk-confirm", response_model=BulkConfirmResponse)
async def bulk_confirm_use_cases(
    id: str,
    request: BulkConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm bulk upload and create UseCase records.
    Skips rows with empty name field.
    """
    # Verify project exists and belongs to current user
    result = await db.execute(select(Project).where(Project.id == id, Project.created_by == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create UseCase records from request rows
    use_cases = []
    for row in request.rows:
        # Get name from mapped column
        name = row.get(request.column_mapping.name, "").strip()
        if not name:
            # Skip rows with empty name
            continue

        # Get optional fields
        description = None
        if request.column_mapping.description:
            description = row.get(request.column_mapping.description, "").strip()
            description = description if description else None

        source_platform = None
        if request.column_mapping.source_platform:
            source_platform = row.get(request.column_mapping.source_platform, "").strip()
            source_platform = source_platform if source_platform else None

        install_status = None
        if request.column_mapping.install_status:
            install_status = row.get(request.column_mapping.install_status, "").strip()
            install_status = install_status if install_status else None

        # Create UseCase record
        use_case = UseCase(
            project_id=id,
            name=name,
            description=description,
            source_platform=source_platform,
            install_status=install_status,
        )
        use_cases.append(use_case)

    # Batch insert
    if use_cases:
        db.add_all(use_cases)
        await db.commit()
        # Refresh to get IDs
        for uc in use_cases:
            await db.refresh(uc)

    return BulkConfirmResponse(created=len(use_cases), use_case_ids=[uc.id for uc in use_cases])
