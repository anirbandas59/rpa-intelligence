"""
Integration test for bulk upload flow.

Tests the complete bulk upload workflow from file upload to processing.
"""

from pathlib import Path

import pytest

from services.file_storage_service import file_storage_service


@pytest.mark.asyncio
async def test_file_storage_service_csv():
    """Test CSV file upload and session creation."""
    # Read test CSV
    test_file = Path(__file__).parent.parent / "data" / "temp" / "test_bulk_upload.csv"
    if not test_file.exists():
        pytest.skip("Test CSV file not found")

    content = test_file.read_bytes()

    # Create session
    session = file_storage_service.create_upload_session(
        file_content=content,
        filename="test_upload.csv",
        project_id="test-project-123",
        user_id="test-user-456",
    )

    # Verify session
    assert session.id is not None
    assert session.filename == "test_upload.csv"
    assert session.row_count == 5  # Based on test file
    assert len(session.columns["columns"]) == 4  # Process Name, Description, Platform, Status

    # Get preview
    preview = file_storage_service.get_preview_rows(session, limit=2)
    assert len(preview) == 2
    assert "Process Name" in preview[0]
    assert preview[0]["Process Name"] == "Invoice Processing Bot"

    # Cleanup
    Path(session.file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_parse_file_with_mapping():
    """Test file parsing with column mapping."""
    # Read test CSV
    test_file = Path(__file__).parent.parent / "data" / "temp" / "test_bulk_upload.csv"
    if not test_file.exists():
        pytest.skip("Test CSV file not found")

    content = test_file.read_bytes()

    # Create session
    session = file_storage_service.create_upload_session(
        file_content=content,
        filename="test_upload.csv",
        project_id="test-project-123",
        user_id="test-user-456",
    )

    # Parse with mapping
    column_mapping = {
        "name": "Process Name",
        "description": "Description",
        "source_platform": "Platform",
        "install_status": "Status",
    }

    use_cases = []
    async for batch in file_storage_service.parse_file_with_mapping(
        session=session,
        column_mapping=column_mapping,
        batch_size=10,
    ):
        use_cases.extend(batch)

    # Verify results
    assert len(use_cases) == 5
    assert use_cases[0].name == "Invoice Processing Bot"
    assert use_cases[0].description == "Automated invoice data extraction"
    assert use_cases[0].source_platform == "UiPath"
    assert use_cases[0].install_status == "Production"

    # Cleanup
    Path(session.file_path).unlink(missing_ok=True)
