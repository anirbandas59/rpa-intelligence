"""
Integration test for Stage 3 timeline flow.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app
from db.session import get_session_factory, get_engine
from db.models import Base, User, Project, UseCase, StageRun
from auth import hash_password, create_access_token


@pytest.fixture
async def db_session():
    """Create a test database session."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory(engine)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_project(db_session, test_user):
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="Test project for Stage 3",
        created_by=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_use_case(db_session, test_project):
    """Create a test use case with S3 inputs."""
    use_case = UseCase(
        project_id=test_project.id,
        name="Test Use Case",
        description="Test use case for timeline",
        s3_inputs={
            "effort_weeks": 6,
            "start_date": "2025-07-01",
            "complexity_class": "L",
        },
    )
    db_session.add(use_case)
    await db_session.commit()
    await db_session.refresh(use_case)
    return use_case


@pytest.fixture
def auth_headers(test_user):
    """Generate auth headers."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_update_s3_inputs(test_use_case, auth_headers):
    """Test updating Stage 3 inputs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/use-cases/{test_use_case.id}/s3/inputs",
            json={
                "effort_weeks": 8,
                "start_date": "2025-08-01",
                "complexity_class": "XL",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["s3_inputs"]["effort_weeks"] == 8
        assert data["s3_inputs"]["start_date"] == "2025-08-01"
        assert data["s3_inputs"]["complexity_class"] == "XL"


@pytest.mark.asyncio
async def test_create_s3_run(test_use_case, auth_headers):
    """Test creating a Stage 3 run."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "complete"
        assert "result" in data
        assert "phases" in data["result"]
        assert len(data["result"]["phases"]) == 6
        assert data["result"]["total_weeks"] > 0


@pytest.mark.asyncio
async def test_list_s3_runs(test_use_case, auth_headers, db_session):
    """Test listing Stage 3 runs."""
    # Create a run first
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs",
            headers=auth_headers,
        )

        # List runs
        response = await client.get(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert len(data["runs"]) >= 1
        assert data["runs"][0]["run_number"] == 1


@pytest.mark.asyncio
async def test_get_s3_run(test_use_case, auth_headers):
    """Test getting a single Stage 3 run."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a run
        create_response = await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs",
            headers=auth_headers,
        )
        run_id = create_response.json()["run_id"]

        # Get the run
        response = await client.get(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs/{run_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id
        assert "inputs_snapshot" in data
        assert "result" in data
        assert data["status"] == "complete"


@pytest.mark.asyncio
async def test_phase_delta_adjustment(test_use_case, auth_headers):
    """Test adjusting phase with delta."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Apply delta
        response = await client.patch(
            f"/api/v1/use-cases/{test_use_case.id}/s3/phase-delta",
            json={
                "phase_name": "build",
                "delta_weeks": 2,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "phase_deltas" in data
        assert data["phase_deltas"]["build"] == 2

        # Create run to verify delta is applied
        run_response = await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/runs",
            headers=auth_headers,
        )

        assert run_response.status_code == 200
        run_data = run_response.json()
        build_phase = next(p for p in run_data["result"]["phases"] if p["name"] == "Build")
        # Original 6 weeks + 2 delta = 8 weeks
        assert build_phase["weeks"] == 8
        assert build_phase["is_delta"] is True


@pytest.mark.asyncio
async def test_reset_phase_deltas(test_use_case, auth_headers):
    """Test resetting phase deltas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Add delta
        await client.patch(
            f"/api/v1/use-cases/{test_use_case.id}/s3/phase-delta",
            json={"phase_name": "build", "delta_weeks": 3},
            headers=auth_headers,
        )

        # Reset deltas
        response = await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/reset-deltas",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "phase_deltas" not in data["s3_inputs"]


@pytest.mark.asyncio
async def test_load_from_s2(test_use_case, auth_headers, db_session):
    """Test loading effort and complexity from Stage 2."""
    # Create a mock S2 run
    s2_run = StageRun(
        use_case_id=test_use_case.id,
        stage="s2",
        run_number=1,
        inputs_snapshot={},
        inputs_hash="test_hash",
        result={
            "complexity_class": "XL",
            "effort_min_weeks": 6,
            "effort_max_weeks": 8,
            "total_score": 25,
        },
        status="complete",
    )
    db_session.add(s2_run)
    test_use_case.s2_latest_run_id = s2_run.id
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/use-cases/{test_use_case.id}/s3/load-from-s2",
            json={"prefer_max": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["loaded_values"]["effort_weeks"] == 8  # max
        assert data["loaded_values"]["complexity_class"] == "XL"
        assert data["s3_inputs"]["effort_weeks_source"] == "from_s2"
        assert data["s3_inputs"]["complexity_class_source"] == "from_s2"


@pytest.mark.asyncio
async def test_s3_run_without_inputs(auth_headers, db_session, test_project):
    """Test that S3 run fails without required inputs."""
    # Create use case without s3_inputs
    use_case = UseCase(
        project_id=test_project.id,
        name="Empty Use Case",
        description="No inputs",
    )
    db_session.add(use_case)
    await db_session.commit()
    await db_session.refresh(use_case)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/use-cases/{use_case.id}/s3/runs",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "effort_weeks required" in response.json()["detail"]
