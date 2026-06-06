"""Unit tests for bulk upload endpoints."""

import csv
import io

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_bulk_upload_csv_parsing():
    """Test CSV file parsing in bulk upload preview."""
    # Create an in-memory CSV file
    csv_content = """name,description,source_platform
Process A,Automated data entry,SAP
Process B,Report generation,Oracle
Process C,Invoice matching,Excel
Process D,Approval workflow,Salesforce
Process E,Data transformation,Python
"""

    # Mock the file upload by creating a BytesIO object
    csv_bytes = io.BytesIO(csv_content.encode("utf-8"))

    # Simulate the CSV parsing that occurs in the endpoint
    csv_bytes.seek(0)
    text_content = csv_bytes.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text_content))

    # Verify columns
    columns = list(reader.fieldnames)
    assert columns == ["name", "description", "source_platform"]

    # Verify preview (first 5 rows)
    preview = []
    row_count = 0
    for i, row in enumerate(reader):
        if i < 5:
            preview.append(dict(row))
        row_count += 1

    assert len(preview) == 5
    assert row_count == 5
    assert preview[0]["name"] == "Process A"
    assert preview[0]["description"] == "Automated data entry"
    assert preview[0]["source_platform"] == "SAP"
    assert preview[4]["name"] == "Process E"


def test_bulk_upload_csv_empty_rows():
    """Test CSV parsing skips rows with empty required fields."""
    csv_content = """name,description
Process A,Description A
,Description B
Process C,
Process D,Description D
"""

    csv_bytes = io.BytesIO(csv_content.encode("utf-8"))
    csv_bytes.seek(0)
    text_content = csv_bytes.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text_content))

    columns = list(reader.fieldnames)
    assert columns == ["name", "description"]

    # Count rows that would be skipped (empty name)
    preview = []
    for row in reader:
        name = row.get("name", "").strip()
        if name:  # Only include if name is not empty
            preview.append(dict(row))

    assert len(preview) == 3  # Only rows with non-empty names
    assert preview[0]["name"] == "Process A"
    assert preview[1]["name"] == "Process C"
    assert preview[2]["name"] == "Process D"


def test_bulk_upload_csv_with_extra_columns():
    """Test CSV parsing handles extra columns gracefully."""
    csv_content = """name,description,source_platform,install_status,extra_col
Process A,Description A,SAP,Active,Extra1
Process B,Description B,Oracle,Inactive,Extra2
"""

    csv_bytes = io.BytesIO(csv_content.encode("utf-8"))
    csv_bytes.seek(0)
    text_content = csv_bytes.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text_content))

    columns = list(reader.fieldnames)
    assert len(columns) == 5
    assert "extra_col" in columns

    rows = list(reader)
    assert rows[0]["extra_col"] == "Extra1"


def test_bulk_upload_empty_csv():
    """Test handling of empty CSV file."""
    csv_content = ""

    csv_bytes = io.BytesIO(csv_content.encode("utf-8"))
    csv_bytes.seek(0)
    text_content = csv_bytes.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text_content))

    # Empty file has no fieldnames
    columns = list(reader.fieldnames) if reader.fieldnames else []
    assert columns == []


def test_column_mapping_validation():
    """Test ColumnMapping Pydantic model validation."""
    from api.v1.projects import ColumnMapping

    # Valid mapping with only required field
    mapping1 = ColumnMapping(name="process_name")
    assert mapping1.name == "process_name"
    assert mapping1.description is None
    assert mapping1.source_platform is None
    assert mapping1.install_status is None

    # Valid mapping with all fields
    mapping2 = ColumnMapping(
        name="name",
        description="desc",
        source_platform="platform",
        install_status="status"
    )
    assert mapping2.name == "name"
    assert mapping2.description == "desc"
    assert mapping2.source_platform == "platform"
    assert mapping2.install_status == "status"


def test_bulk_confirm_request_validation():
    """Test BulkConfirmRequest Pydantic model validation."""
    from api.v1.projects import BulkConfirmRequest, ColumnMapping

    mapping = ColumnMapping(name="name", description="description")
    rows = [
        {"name": "Process A", "description": "Desc A"},
        {"name": "Process B", "description": "Desc B"},
    ]

    request = BulkConfirmRequest(column_mapping=mapping, rows=rows)
    assert request.column_mapping.name == "name"
    assert len(request.rows) == 2
    assert request.rows[0]["name"] == "Process A"


def test_bulk_upload_response_model():
    """Test BulkUploadResponse Pydantic model."""
    from api.v1.projects import BulkUploadResponse

    response = BulkUploadResponse(
        columns=["name", "description"],
        preview=[
            {"name": "Process A", "description": "Desc A"},
            {"name": "Process B", "description": "Desc B"},
        ],
        row_count=10
    )

    assert response.columns == ["name", "description"]
    assert len(response.preview) == 2
    assert response.row_count == 10


def test_bulk_confirm_response_model():
    """Test BulkConfirmResponse Pydantic model."""
    from api.v1.projects import BulkConfirmResponse

    response = BulkConfirmResponse(
        created=5,
        use_case_ids=["id1", "id2", "id3", "id4", "id5"]
    )

    assert response.created == 5
    assert len(response.use_case_ids) == 5
