"""
Stage 1 integration test — verify assessment service works end-to-end.
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select as sa_select
from db.session import Base
from db.models import UseCase, Project, User, StageRun
from services.assessment_service import AssessmentService


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        # Create test user (skip password hashing in tests)
        user = User(
            email="test@example.com",
            hashed_password="test_hash",
            role="user",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create test project
        project = Project(
            name="Test Project",
            created_by=user.id,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)

        # Create test use-case
        use_case = UseCase(
            project_id=project.id,
            name="Invoice Processing Bot",
            description="Automated invoice extraction and validation using UiPath Document Understanding",
            source_platform="UiPath",
            install_status="Production",
        )
        session.add(use_case)
        await session.commit()
        await session.refresh(use_case)

        yield session, use_case


@pytest.mark.asyncio
async def test_assessment_service_creates_stage_run(test_db):
    """Test that assessment service creates a StageRun record."""
    session, use_case = test_db

    # Mock LLM response
    mock_response = """{
        "technical_feasibility": 30,
        "migration_effort": 20,
        "platform_suitability": 15,
        "risk": 10,
        "total_score": 75,
        "migration_decision": "QUICK_WIN",
        "confidence": "HIGH",
        "analysis": "This invoice processing automation is well-suited for Power Automate migration.",
        "blockers": [],
        "power_automate_fit": "Excellent fit - Power Automate has strong document processing capabilities."
    }"""

    service = AssessmentService(session, model="claude-haiku-4-5")

    with patch.object(service.llm, 'complete', return_value=mock_response):
        stage_run = await service.run_assessment(use_case.id)

    # Verify StageRun was created
    assert stage_run is not None
    assert stage_run.stage == "s1"
    assert stage_run.status == "complete"
    assert stage_run.run_number == 1
    assert stage_run.model_used == "claude-haiku-4-5"

    # Verify result
    result = stage_run.result
    assert result["technical_feasibility"] == 30
    assert result["migration_effort"] == 20
    assert result["platform_suitability"] == 15
    assert result["risk"] == 10
    assert result["total_score"] == 75
    assert result["migration_decision"] == "QUICK_WIN"
    assert result["confidence"] == "HIGH"

    # Verify inputs snapshot
    assert stage_run.inputs_snapshot["name"] == "Invoice Processing Bot"
    assert "UiPath Document Understanding" in stage_run.inputs_snapshot["description"]

    # Verify use-case updated
    updated_result = await session.execute(
        sa_select(UseCase).where(UseCase.id == use_case.id)
    )
    updated_uc = updated_result.scalar_one_or_none()
    assert updated_uc.s1_latest_run_id == stage_run.id


@pytest.mark.asyncio
async def test_assessment_handles_malformed_json(test_db):
    """Test that assessment service handles malformed JSON responses."""
    session, use_case = test_db

    # Mock LLM response with markdown fences
    mock_response = """Here's my assessment:

```json
{
    "technical_feasibility": 25,
    "migration_effort": 15,
    "platform_suitability": 12,
    "risk": 8,
    "total_score": 60,
    "migration_decision": "STRATEGIC",
    "confidence": "MEDIUM",
    "analysis": "Moderate complexity automation.",
    "blockers": ["API dependencies"],
    "power_automate_fit": "Good fit with some adjustments."
}
```

Hope this helps!"""

    service = AssessmentService(session, model="claude-haiku-4-5")

    with patch.object(service.llm, 'complete', return_value=mock_response):
        stage_run = await service.run_assessment(use_case.id)

    # Should still parse successfully
    assert stage_run.status == "complete"
    result = stage_run.result
    assert result["technical_feasibility"] == 25
    assert result["total_score"] == 60
    assert result["migration_decision"] == "STRATEGIC"
