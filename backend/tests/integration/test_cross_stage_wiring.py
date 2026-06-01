"""
Phase 6 Integration Test — Cross-Stage Wiring + Staleness Detection

Verifies:
1. Full end-to-end data flow works across all stages
2. Editing target inputs does not modify source StageRun records
3. Staleness detection triggers correctly
4. Load-from endpoints copy data with correct source tags
5. Independent dict semantics (no reference sharing)
"""

import pytest
import hashlib
import json


def compute_inputs_hash(inputs: dict) -> str:
    """Match the hash function used in routes."""
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


@pytest.mark.asyncio
async def test_full_cross_stage_flow(async_client, test_user_token, test_project):
    """
    Full flow: S1 → S2 → S3 (load from S2) → S4 (load from S2 and S3)
    Verify: editing S4 inputs does not change S2 or S3 records.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # ========== Step 1: Create Use Case ==========
    uc_payload = {
        "project_id": test_project["id"],
        "name": "Test End-to-End Process",
        "description": "A test automation for cross-stage wiring verification",
    }

    uc_response = await async_client.post("/api/v1/use-cases", json=uc_payload, headers=headers)
    assert uc_response.status_code == 200
    use_case = uc_response.json()
    use_case_id = use_case["id"]

    # ========== Step 2: Check Initial Readiness ==========
    readiness = await async_client.get(f"/api/v1/use-cases/{use_case_id}/readiness", headers=headers)
    assert readiness.status_code == 200
    status = readiness.json()
    assert status["s1"] == "ready"  # Has name + description
    assert status["s2"] == "not_ready"
    assert status["s3"] == "not_ready"
    assert status["s4"] == "not_ready"

    # ========== Step 3: Run Stage 1 (skipped for speed, mock result) ==========
    # In real test, would call POST /s1/runs
    # For this test, we'll assume S1 completed

    # ========== Step 4: Create Mock Stage 2 Run ==========
    # Update S2 inputs with manual bands
    s2_inputs = {
        "activities": "XL",
        "activities_source": "manual",
        "business_rules": "XL",
        "business_rules_source": "manual",
        "layouts": "L",
        "layouts_source": "manual",
        "interfaces": "S",
        "interfaces_source": "manual",
        "technology": "S",
        "technology_source": "manual",
    }

    update_s2 = await async_client.patch(f"/api/v1/use-cases/{use_case_id}/s2/inputs", json=s2_inputs, headers=headers)
    assert update_s2.status_code == 200

    # Run S2 (manual bands → no LLM)
    s2_run_response = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s2/runs", json={"model": "claude-haiku-4-5"}, headers=headers
    )
    assert s2_run_response.status_code in [200, 202]
    s2_run_id = s2_run_response.json()["run_id"]

    # Poll until S2 background task completes (202 response has no result yet)
    import asyncio
    s2_run_detail = None
    for _ in range(30):
        detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
        if detail.status_code == 200 and detail.json().get("status") == "complete":
            s2_run_detail = detail
            break
        await asyncio.sleep(0.1)
    assert s2_run_detail is not None, "S2 run did not complete in time"

    # Verify S2 result (ground truth: 21 → L)  result is nested under "scoring"
    s2_result = s2_run_detail.json()["result"]
    scoring = s2_result["scoring"]
    assert scoring["total_score"] == 21
    assert scoring["complexity_class"] == "L"
    assert scoring["effort_min_weeks"] == 12
    assert scoring["effort_max_weeks"] == 12

    s2_original_snapshot = s2_run_detail.json()["inputs_snapshot"]
    s2_original_hash = s2_run_detail.json()["inputs_hash"]

    # ========== Step 5: Load S2 data into S3 ==========
    load_s3 = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s3/load-from-s2", json={"prefer_max": True}, headers=headers
    )
    assert load_s3.status_code == 200
    s3_loaded = load_s3.json()

    # Verify loaded values have correct source tags
    assert s3_loaded["s3_inputs"]["effort_weeks"] == 12  # max from S2
    assert s3_loaded["s3_inputs"]["effort_weeks_source"] == "from_s2"
    assert s3_loaded["s3_inputs"]["complexity_class"] == "L"
    assert s3_loaded["s3_inputs"]["complexity_class_source"] == "from_s2"

    # Add start_date to S3 inputs
    s3_update = await async_client.patch(
        f"/api/v1/use-cases/{use_case_id}/s3/inputs", json={"start_date": "2026-07-01"}, headers=headers
    )
    assert s3_update.status_code == 200

    # Run S3
    s3_run_response = await async_client.post(f"/api/v1/use-cases/{use_case_id}/s3/runs", headers=headers)
    assert s3_run_response.status_code == 200
    s3_run = s3_run_response.json()
    s3_run_id = s3_run["run_id"]

    # Verify S3 result
    s3_result = s3_run["result"]
    assert "phases" in s3_result
    assert "total_weeks" in s3_result

    # Get S3 run for later comparison
    s3_run_detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s3/runs/{s3_run_id}", headers=headers)
    assert s3_run_detail.status_code == 200
    s3_original_snapshot = s3_run_detail.json()["inputs_snapshot"]
    s3_original_hash = s3_run_detail.json()["inputs_hash"]

    # ========== Step 6: Load S2 and S3 data into S4 ==========
    load_s4_from_s2 = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s4/load-from-s2", json={}, headers=headers
    )
    assert load_s4_from_s2.status_code == 200
    s4_from_s2 = load_s4_from_s2.json()

    # Verify S4 loaded S2 data with source tags
    assert s4_from_s2["s4_inputs"]["complexity_class"] == "L"
    assert s4_from_s2["s4_inputs"]["complexity_class_source"] == "from_s2"

    load_s4_from_s3 = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s4/load-from-s3", json={}, headers=headers
    )
    assert load_s4_from_s3.status_code == 200
    s4_from_s3 = load_s4_from_s3.json()

    # Verify S4 loaded S3 data with source tags
    assert "sprint_count" in s4_from_s3["s4_inputs"]
    assert s4_from_s3["s4_inputs"]["sprint_count_source"] == "from_s3"

    # ========== Step 7: Edit S4 inputs ==========
    s4_edit = await async_client.patch(
        f"/api/v1/use-cases/{use_case_id}/s4/inputs", json={"sprint_count": 10, "sprint_capacity": 13}, headers=headers
    )
    assert s4_edit.status_code == 200

    # ========== Step 8: Verify S2 and S3 records unchanged ==========
    # Re-fetch S2 run
    s2_after = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
    assert s2_after.status_code == 200
    s2_after_data = s2_after.json()

    # Verify S2 inputs_snapshot unchanged
    assert s2_after_data["inputs_snapshot"] == s2_original_snapshot
    assert s2_after_data["inputs_hash"] == s2_original_hash

    # Re-fetch S3 run
    s3_after = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s3/runs/{s3_run_id}", headers=headers)
    assert s3_after.status_code == 200
    s3_after_data = s3_after.json()

    # Verify S3 inputs_snapshot unchanged
    assert s3_after_data["inputs_snapshot"] == s3_original_snapshot
    assert s3_after_data["inputs_hash"] == s3_original_hash

    print("✅ Phase 6 Test Passed: Editing S4 inputs did NOT modify S2 or S3 records")


@pytest.mark.asyncio
async def test_staleness_detection(async_client, test_user_token, test_project):
    """
    Verify staleness indicator appears after input edit, clears after re-run.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Create use case
    uc_response = await async_client.post(
        "/api/v1/use-cases",
        json={
            "project_id": test_project["id"],
            "name": "Staleness Test Process",
            "description": "Testing staleness detection",
        },
        headers=headers,
    )
    use_case_id = uc_response.json()["id"]

    # Set S2 inputs
    s2_inputs = {
        "activities": "M",
        "business_rules": "M",
        "layouts": "M",
        "interfaces": "M",
        "technology": "M",
    }
    await async_client.patch(f"/api/v1/use-cases/{use_case_id}/s2/inputs", json=s2_inputs, headers=headers)

    # Run S2
    s2_run = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s2/runs", json={"model": "claude-haiku-4-5"}, headers=headers
    )
    if s2_run.status_code != 202:
        print(f"S2 run error: {s2_run.json()}")
    assert s2_run.status_code == 202
    s2_run_id = s2_run.json()["run_id"]

    # Poll until S2 background task completes
    import asyncio
    for _ in range(30):
        detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
        if detail.status_code == 200 and detail.json().get("status") == "complete":
            break
        await asyncio.sleep(0.1)

    # Check readiness — should be complete
    readiness_1 = await async_client.get(f"/api/v1/use-cases/{use_case_id}/readiness", headers=headers)
    status_1 = readiness_1.json()
    assert status_1["s2"] == "complete"

    # Edit S2 inputs (change a band)
    await async_client.patch(
        f"/api/v1/use-cases/{use_case_id}/s2/inputs",
        json={"activities": "L"},  # Changed from M to L
        headers=headers,
    )

    # Check readiness — should be stale
    readiness_2 = await async_client.get(f"/api/v1/use-cases/{use_case_id}/readiness", headers=headers)
    status_2 = readiness_2.json()
    assert status_2["s2"] == "stale"

    # Re-run S2
    s2_rerun = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s2/runs", json={"model": "claude-haiku-4-5"}, headers=headers
    )
    assert s2_rerun.status_code in [200, 202]
    s2_rerun_id = s2_rerun.json()["run_id"]

    # Poll until re-run completes
    for _ in range(30):
        detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_rerun_id}", headers=headers)
        if detail.status_code == 200 and detail.json().get("status") == "complete":
            break
        await asyncio.sleep(0.1)

    # Check readiness — should be complete again
    readiness_3 = await async_client.get(f"/api/v1/use-cases/{use_case_id}/readiness", headers=headers)
    status_3 = readiness_3.json()
    assert status_3["s2"] == "complete"

    print("✅ Staleness Test Passed: stale → edit → stale, re-run → complete")


@pytest.mark.asyncio
async def test_load_from_independent_copy(async_client, test_user_token, test_project):
    """
    Verify load-from creates independent copy (no reference sharing).
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Create use case
    uc_response = await async_client.post(
        "/api/v1/use-cases",
        json={
            "project_id": test_project["id"],
            "name": "Independence Test",
            "description": "Testing dict independence",
        },
        headers=headers,
    )
    use_case_id = uc_response.json()["id"]

    # Run S2 with manual bands
    s2_inputs = {
        "activities": "S",
        "business_rules": "S",
        "layouts": "S",
        "interfaces": "S",
        "technology": "S",
    }
    await async_client.patch(f"/api/v1/use-cases/{use_case_id}/s2/inputs", json=s2_inputs, headers=headers)

    s2_run = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s2/runs", json={"model": "claude-haiku-4-5"}, headers=headers
    )
    assert s2_run.status_code in [200, 202]
    s2_run_id = s2_run.json()["run_id"]

    # Poll until S2 background task completes
    import asyncio
    s2_detail = None
    for _ in range(30):
        detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
        if detail.status_code == 200 and detail.json().get("status") == "complete":
            s2_detail = detail
            break
        await asyncio.sleep(0.1)
    assert s2_detail is not None, "S2 run did not complete in time"
    s2_complexity = s2_detail.json()["result"]["scoring"]["complexity_class"]

    # Load into S3
    load_s3 = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s3/load-from-s2", json={"prefer_max": True}, headers=headers
    )
    s3_inputs_before = load_s3.json()["s3_inputs"]
    s3_complexity_before = s3_inputs_before["complexity_class"]

    # Verify initial copy
    assert s3_complexity_before == s2_complexity

    # Modify S3 inputs
    await async_client.patch(
        f"/api/v1/use-cases/{use_case_id}/s3/inputs",
        json={"complexity_class": "XL"},  # Change to XL
        headers=headers,
    )

    # Re-fetch S2 run
    s2_after = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
    s2_complexity_after = s2_after.json()["result"]["scoring"]["complexity_class"]

    # Verify S2 result unchanged
    assert s2_complexity_after == s2_complexity
    assert s2_complexity_after != "XL"  # Should still be original value

    print("✅ Independence Test Passed: S3 modification did NOT affect S2 result")


@pytest.mark.asyncio
async def test_run_history_all_stages(async_client, test_user_token, test_project):
    """
    Verify all stages have run history endpoints with inputs_snapshot + result.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Create use case
    uc_response = await async_client.post(
        "/api/v1/use-cases",
        json={"project_id": test_project["id"], "name": "History Test", "description": "Testing run history"},
        headers=headers,
    )
    use_case_id = uc_response.json()["id"]

    # Run S2 (easiest to test synchronously)
    s2_inputs = {
        "activities": "M",
        "business_rules": "M",
        "layouts": "M",
        "interfaces": "M",
        "technology": "M",
    }
    await async_client.patch(f"/api/v1/use-cases/{use_case_id}/s2/inputs", json=s2_inputs, headers=headers)

    s2_run = await async_client.post(
        f"/api/v1/use-cases/{use_case_id}/s2/runs", json={"model": "claude-haiku-4-5"}, headers=headers
    )
    assert s2_run.status_code in [200, 202]
    s2_run_id = s2_run.json()["run_id"]

    # Poll until S2 background task completes before checking history
    import asyncio
    for _ in range(30):
        detail = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
        if detail.status_code == 200 and detail.json().get("status") == "complete":
            break
        await asyncio.sleep(0.1)

    # Get run history via GET /{run_id}
    s2_history = await async_client.get(f"/api/v1/use-cases/{use_case_id}/s2/runs/{s2_run_id}", headers=headers)
    assert s2_history.status_code == 200
    s2_data = s2_history.json()

    # Verify has both inputs_snapshot and result
    assert "inputs_snapshot" in s2_data
    assert "result" in s2_data
    assert "inputs_hash" in s2_data
    # inputs_snapshot stores s2_inputs directly (for correct staleness hash matching)
    assert s2_data["inputs_snapshot"]["activities"] == s2_inputs["activities"]
    # result is nested: {bands, scoring, extraction_notes, model_used}
    assert "complexity_class" in s2_data["result"]["scoring"]

    print("✅ Run History Test Passed: Full inputs_snapshot + result available")
