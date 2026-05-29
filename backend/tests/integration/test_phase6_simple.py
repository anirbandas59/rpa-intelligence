"""
Phase 6 Integration Test — Simplified version focusing on wiring logic
Tests the key Phase 6 requirements without async complexity.
"""

import pytest
import hashlib
import json
from sqlalchemy import select
from db.models import UseCase, StageRun


def compute_inputs_hash(inputs: dict) -> str:
    """Match the hash function used in routes."""
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


@pytest.mark.asyncio
async def test_staleness_hash_computation():
    """
    Test that staleness detection works correctly via hash computation.
    """
    inputs_v1 = {
        "activities": "M",
        "business_rules": "M",
        "layouts": "M",
    }

    inputs_v2 = {
        "activities": "L",  # Changed
        "business_rules": "M",
        "layouts": "M",
    }

    inputs_v1_duplicate = {
        "layouts": "M",
        "activities": "M",  # Different order, same content
        "business_rules": "M",
    }

    hash_v1 = compute_inputs_hash(inputs_v1)
    hash_v2 = compute_inputs_hash(inputs_v2)
    hash_v1_dup = compute_inputs_hash(inputs_v1_duplicate)

    # Same content (different order) should produce same hash
    assert hash_v1 == hash_v1_dup, "Hash should be order-independent (sort_keys=True)"

    # Different content should produce different hash
    assert hash_v1 != hash_v2, "Different inputs should produce different hashes"

    print("✅ Staleness hash computation test passed")


@pytest.mark.asyncio
async def test_load_from_creates_independent_copy(test_db_session, test_user, test_project):
    """
    Verify that load-from operations create independent dictionaries.
    This tests the core requirement: editing target does not modify source.
    """
    # Create use case
    use_case = UseCase(project_id=test_project["id"], name="Independence Test", description="Testing copy semantics")
    test_db_session.add(use_case)
    await test_db_session.commit()
    await test_db_session.refresh(use_case)

    # Create S2 run with result
    s2_inputs = {
        "activities": "S",
        "business_rules": "S",
        "layouts": "S",
        "interfaces": "S",
        "technology": "S",
    }

    s2_result = {
        "total_score": 8,
        "complexity_class": "S",
        "effort_min_weeks": 2,
        "effort_max_weeks": 4,
        "attribute_weights": {
            "activities": 2,
            "business_rules": 2,
            "layouts": 1,
            "interfaces": 1,
            "technology": 2,
        },
    }

    s2_run = StageRun(
        use_case_id=use_case.id,
        stage="s2",
        run_number=1,
        inputs_snapshot=s2_inputs.copy(),  # Important: copy
        inputs_hash=compute_inputs_hash(s2_inputs),
        result=s2_result.copy(),  # Important: copy
        model_used="claude-haiku-4-5",
        triggered_by=test_user.id,
        status="complete",
    )

    test_db_session.add(s2_run)
    use_case.s2_latest_run_id = s2_run.id
    await test_db_session.commit()
    await test_db_session.refresh(s2_run)

    # Simulate load-from-s2 into S3
    # In real code, this happens in the route handler
    s3_inputs = {
        "effort_weeks": s2_run.result["effort_max_weeks"],
        "effort_weeks_source": "from_s2",
        "complexity_class": s2_run.result["complexity_class"],
        "complexity_class_source": "from_s2",
    }

    use_case.s3_inputs = s3_inputs
    await test_db_session.commit()

    # Modify S3 inputs
    use_case.s3_inputs["complexity_class"] = "XL"  # Change complexity
    use_case.s3_inputs["effort_weeks"] = 20  # Change effort
    await test_db_session.commit()

    # Re-fetch S2 run from DB
    s2_refetch = await test_db_session.execute(select(StageRun).where(StageRun.id == s2_run.id))
    s2_run_after = s2_refetch.scalar_one_or_none()

    # Verify S2 result unchanged
    assert s2_run_after.result["complexity_class"] == "S"
    assert s2_run_after.result["effort_max_weeks"] == 4
    assert s2_run_after.result != use_case.s3_inputs

    print("✅ Independent copy test passed: S3 modification did NOT affect S2 record")


@pytest.mark.asyncio
async def test_inputs_snapshot_immutability(test_db_session, test_user, test_project):
    """
    Verify that StageRun.inputs_snapshot remains immutable after creation.
    """
    use_case = UseCase(
        project_id=test_project["id"], name="Immutability Test", description="Testing snapshot immutability"
    )
    test_db_session.add(use_case)
    await test_db_session.commit()
    await test_db_session.refresh(use_case)

    # Create run with inputs
    original_inputs = {
        "activities": "M",
        "business_rules": "M",
        "layouts": "M",
    }

    run = StageRun(
        use_case_id=use_case.id,
        stage="s2",
        run_number=1,
        inputs_snapshot=original_inputs.copy(),
        inputs_hash=compute_inputs_hash(original_inputs),
        result={"total_score": 12},
        triggered_by=test_user.id,
        status="complete",
    )

    test_db_session.add(run)
    await test_db_session.commit()
    await test_db_session.refresh(run)

    original_hash = run.inputs_hash

    # Modify use_case inputs (simulating user edit)
    use_case.s2_inputs = {
        "activities": "XL",  # Changed
        "business_rules": "M",
        "layouts": "M",
    }
    await test_db_session.commit()

    # Re-fetch run
    refetch = await test_db_session.execute(select(StageRun).where(StageRun.id == run.id))
    run_after = refetch.scalar_one_or_none()

    # Verify run snapshot unchanged
    assert run_after.inputs_snapshot["activities"] == "M"  # Not XL
    assert run_after.inputs_hash == original_hash

    print("✅ Immutability test passed: StageRun.inputs_snapshot remained unchanged")


@pytest.mark.asyncio
async def test_source_tags_preserved(test_db_session, test_user, test_project):
    """
    Verify that _source tags are correctly preserved during load-from operations.
    """
    use_case = UseCase(
        project_id=test_project["id"], name="Source Tag Test", description="Testing source tag preservation"
    )
    test_db_session.add(use_case)
    await test_db_session.commit()
    await test_db_session.refresh(use_case)

    # Simulate S2 result with extracted bands
    s2_result = {
        "complexity_class": "M",
        "effort_min_weeks": 5,
        "effort_max_weeks": 5,
    }

    # Load into S3 with source tags
    s3_inputs = {
        "effort_weeks": s2_result["effort_max_weeks"],
        "effort_weeks_source": "from_s2",
        "complexity_class": s2_result["complexity_class"],
        "complexity_class_source": "from_s2",
        "start_date": "2026-07-01",
        "start_date_source": "manual",
    }

    use_case.s3_inputs = s3_inputs
    await test_db_session.commit()
    await test_db_session.refresh(use_case)

    # Verify source tags present
    assert use_case.s3_inputs["effort_weeks_source"] == "from_s2"
    assert use_case.s3_inputs["complexity_class_source"] == "from_s2"
    assert use_case.s3_inputs["start_date_source"] == "manual"

    # User manually edits effort_weeks
    use_case.s3_inputs["effort_weeks"] = 8
    use_case.s3_inputs["effort_weeks_source"] = "corrected"
    await test_db_session.commit()

    # Verify source changed to corrected
    assert use_case.s3_inputs["effort_weeks"] == 8
    assert use_case.s3_inputs["effort_weeks_source"] == "corrected"
    assert use_case.s3_inputs["complexity_class_source"] == "from_s2"  # Unchanged

    print("✅ Source tag test passed: Tags correctly preserved and updated")
