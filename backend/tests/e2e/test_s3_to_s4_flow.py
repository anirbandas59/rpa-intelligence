#!/usr/bin/env python3
"""
S3 → S4 WBS Grouping & Sprint Assignment Flow Test

Validates complete S3 → S4 data flow with task breakdown prerequisites.
Tests the following workflow:
1. Verify S3 completion (timeline + task decomposition)
2. Load S3 task breakdown into S4 inputs
3. Set sprint parameters
4. Trigger S4 run (WBS grouping + sprint assignment)
5. Wait for S4 completion
6. Verify WBS grouping constraints
7. Verify sprint assignment integrity

Requires S3 task decomposition to be complete.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Configuration
UC_ID = "a6478c03-ec2c-41c9-b572-058f18fbb937"  # Same as main E2E test
BASE_URL = "http://localhost:8000/api/v1"
USE_CASES_BASE = f"{BASE_URL}/use-cases"
MAX_WAIT_TIME = 300  # 3 minutes for S4 WBS grouping
POLL_INTERVAL = 5  # seconds

# Authentication
AUTH_EMAIL = "test123@example.com"
AUTH_PASSWORD = "testpass123"
access_token = None

# Test results storage
results = {}


def authenticate():
    """Login and get access token"""
    global access_token

    print_header("AUTHENTICATION")

    # Try to login
    print("Step 1: Attempting login...")
    resp = requests.post(
        f"{BASE_URL.replace('/api/v1', '')}/api/v1/auth/login", json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD}
    )

    if resp.status_code == 200:
        access_token = resp.json()["access_token"]
        print("✓ Login successful")
        print(f"  Token: {access_token[:20]}...")
        return True

    # If login failed, try to register
    print("  Login failed, attempting registration...")
    resp = requests.post(
        f"{BASE_URL.replace('/api/v1', '')}/api/v1/auth/register",
        json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD, "full_name": "E2E Test User"},
    )

    if resp.status_code == 200:
        print("✓ Registration successful, logging in...")
        resp = requests.post(
            f"{BASE_URL.replace('/api/v1', '')}/api/v1/auth/login",
            json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD},
        )
        if resp.status_code == 200:
            access_token = resp.json()["access_token"]
            print("✓ Login successful")
            return True

    print(f"✗ Authentication failed: {resp.text}")
    return False


def get_headers():
    """Get authorization headers"""
    if access_token:
        return {"Authorization": f"Bearer {access_token}"}
    return {}


def print_header(text):
    """Print section header"""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def verify_s3_complete():
    """Verify S3 timeline and task decomposition are both complete"""
    print_header("STEP 1: Verify S3 Completion (Timeline + Task Decomposition)")

    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get use-case: {resp.text}")
        return None

    uc = resp.json()
    s3_latest_run_id = uc.get("s3_latest_run_id")

    if not s3_latest_run_id:
        print("✗ No S3 run found. Run S2→S3 test first:")
        print("  cd backend && uv run python tests/e2e/test_s2_to_s3_flow.py")
        return None

    print(f"✓ S3 run exists: {s3_latest_run_id}")

    # Get S3 timeline result
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}/s3/runs/{s3_latest_run_id}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get S3 run: {resp.text}")
        return None

    s3_run = resp.json()
    if s3_run["status"] != "complete":
        print(f"✗ S3 run not complete (status: {s3_run['status']})")
        return None

    s3_result = s3_run["result"]
    print(f"✓ S3 Timeline Status: {s3_run['status']}")
    print(f"  - Total Weeks: {s3_result.get('total_weeks')}")
    print(f"  - Phases: {len(s3_result.get('phases', []))}")

    build_sit = s3_result.get("build_sit_window", {})
    print(f"  - Build+SIT Window: {build_sit.get('start_date')} to {build_sit.get('end_date')}")

    # Verify task decomposition
    s3_inputs = uc.get("s3_inputs", {})
    task_extraction = s3_inputs.get("task_extraction", {})

    if not task_extraction:
        print("\n✗ No task decomposition found. Run S2→S3 test with task decomposition:")
        print("  cd backend && uv run python tests/e2e/test_s2_to_s3_flow.py")
        return None

    extraction_status = task_extraction.get("extraction_status")
    verification_passed = task_extraction.get("verification_passed")
    total_net_hours = task_extraction.get("total_net_hours", 0)
    activities = task_extraction.get("activities", [])

    print(f"\n✓ Task Decomposition Status: {extraction_status}")
    print(f"  - Activities: {len(activities)}")
    print(f"  - Total Net Hours: {total_net_hours}h")
    print(f"  - Verification Passed: {verification_passed}")

    if extraction_status != "complete":
        print(f"\n✗ Task decomposition not complete (status: {extraction_status})")
        return None

    if not verification_passed:
        print("\n✗ Task decomposition verification failed")
        return None

    results["s3_run"] = {"run_id": s3_latest_run_id, "result": s3_result}
    results["s3_task_extraction"] = task_extraction
    results["s3_inputs"] = s3_inputs

    return s3_latest_run_id


def load_s3_to_s4():
    """Load S3 task breakdown into S4 inputs"""
    print_header("STEP 2: Load S3 Task Breakdown into S4 Inputs")

    resp = requests.post(
        f"{USE_CASES_BASE}/{UC_ID}/s4/load-from-s3",
        json={},
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Load failed: {resp.text}")
        return False

    print("✓ S3 task breakdown validated for S4")

    # Verify task_extraction is still in S3 inputs (S4 reads from there, doesn't copy)
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}", headers=get_headers())
    uc = resp.json()
    s3_inputs = uc.get("s3_inputs", {})
    s4_inputs = uc.get("s4_inputs", {})

    # Task extraction should remain in s3_inputs (not copied to s4_inputs)
    task_extraction = s3_inputs.get("task_extraction")
    if not task_extraction:
        print("  ✗ task_extraction not found in S3 inputs")
        return False

    print(f"  - Activities: {len(task_extraction.get('activities', []))}")
    print(f"  - Total hours: {task_extraction.get('total_net_hours')}h")
    print(f"  - S4 sprint count: {s4_inputs.get('sprint_count')}")

    results["s4_inputs_loaded"] = s4_inputs
    results["task_extraction_verified"] = task_extraction

    return True


def set_sprint_params():
    """Set sprint parameters for S4"""
    print_header("STEP 3: Set Sprint Parameters")

    # Calculate sprint count based on total weeks from S3
    s3_result = results["s3_run"]["result"]
    total_weeks = s3_result.get("total_weeks", 10)
    sprint_length = 2  # 2-week sprints
    sprint_count = max(1, total_weeks // sprint_length)

    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s4/inputs",
        json={"sprint_count": sprint_count, "sprint_length_weeks": sprint_length},
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Update failed: {resp.text}")
        return False

    print("✓ Sprint parameters set:")
    print(f"  - Sprint count: {sprint_count}")
    print(f"  - Sprint length: {sprint_length} weeks")
    print(f"  - Based on S3 total weeks: {total_weeks}")

    results["sprint_config"] = {"sprint_count": sprint_count, "sprint_length_weeks": sprint_length}

    return True


def trigger_s4_run():
    """Trigger S4 run (WBS grouping + sprint assignment)"""
    print_header("STEP 4: Trigger S4 Run (WBS Grouping + Sprint Assignment)")

    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s4/runs", json={}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Run failed: {resp.text}")
        return None

    run_data = resp.json()
    s4_run_id = run_data["run_id"]
    status = run_data["status"]

    print(f"✓ S4 run created: {s4_run_id}")
    print(f"✓ Status: {status}")

    if status == "running":
        print("  ℹ️  S4 run started in background (WBS grouping + sprint assignment)")
    elif status == "complete":
        print("  ℹ️  S4 run completed immediately")

    results["s4_run_id"] = s4_run_id

    return s4_run_id


def wait_for_s4_completion():
    """Wait for S4 run to complete"""
    print_header("STEP 5: Wait for S4 Completion (Background Job)")
    print("S4 WBS grouping runs asynchronously (30-120 seconds)...")
    print("Polling readiness endpoint every 3 seconds...\n")

    elapsed = 0
    s4_status = "unknown"

    while elapsed < MAX_WAIT_TIME:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        # Check readiness
        resp = requests.get(f"{BASE_URL}/use-cases/{UC_ID}/readiness", headers=get_headers())

        if resp.status_code == 200:
            readiness = resp.json()
            s4_status = readiness.get("s4", "unknown")

            print(f"  [{elapsed:3d}s] S4 status: {s4_status}")

            if s4_status == "complete":
                print("\n✓ S4 run complete!")
                return True
            elif s4_status == "failed":
                print("\n✗ S4 run failed")
                return False
        else:
            print(f"  [{elapsed:3d}s] Readiness check failed: {resp.status_code}")

    print(f"\n✗ S4 run did not complete within {MAX_WAIT_TIME}s (status: {s4_status})")
    return False


def verify_wbs_grouping():
    """Verify WBS grouping meets constraints"""
    print_header("STEP 6: Verify WBS Grouping")

    s4_run_id = results.get("s4_run_id")
    if not s4_run_id:
        print("✗ No S4 run ID found")
        return False

    # Get S4 run result
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}/s4/runs/{s4_run_id}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get S4 run: {resp.text}")
        return False

    s4_run = resp.json()
    if s4_run["status"] != "complete":
        print(f"✗ S4 run not complete (status: {s4_run['status']})")
        return False

    s4_result = s4_run["result"]
    wbs_rows = s4_result.get("wbs_rows", [])
    sequenced_rows = s4_result.get("sequenced_rows", [])
    metadata = s4_result.get("metadata", {})

    print(f"✓ S4 Run Status: {s4_run['status']}")
    print(f"✓ WBS Rows Generated: {len(wbs_rows)}")
    print(f"✓ Sequenced Rows: {len(sequenced_rows)}")

    # Display metadata
    total_rows = metadata.get("total_rows", 0)
    total_hours = metadata.get("total_hours", 0)
    retry_count = metadata.get("retry_count", 0)

    print("\nMetadata:")
    print(f"  - Total Rows: {total_rows}")
    print(f"  - Total Hours: {total_hours}h")
    print(f"  - Retry Count: {retry_count}")

    # Display sample WBS rows
    print("\nSample WBS Rows (first 5):")
    for i, row in enumerate(wbs_rows[:5], 1):
        feature = row.get("feature", "Unnamed")
        hours = row.get("hours", 0)
        priority = row.get("priority", "N/A")
        print(f"  {i}. {feature[:45]:45s} - {hours:5.1f}h ({priority})")

    if len(wbs_rows) > 5:
        print(f"  ... and {len(wbs_rows) - 5} more WBS rows")

    # Display sprint distribution
    sprint_groups = {}
    for row in sequenced_rows:
        sprint_num = row.get("sprint_number", 0)
        if sprint_num not in sprint_groups:
            sprint_groups[sprint_num] = []
        sprint_groups[sprint_num].append(row)

    print(f"\nSprint Distribution ({len(sprint_groups)} sprints):")
    for sprint_num in sorted(sprint_groups.keys()):
        rows = sprint_groups[sprint_num]
        sprint_hours = sum(r.get("hours", 0) for r in rows)
        print(f"  Sprint {sprint_num}: {len(rows)} features, {sprint_hours:.1f}h")

    results["s4_result"] = s4_result

    # Validate constraints
    print_header("VALIDATION")

    # Expected hours from S3 task extraction
    s3_task_extraction = results.get("s3_task_extraction", {})
    expected_hours = s3_task_extraction.get("total_net_hours", 0)

    validations = [
        (len(wbs_rows) > 0, f"Must have at least 1 WBS row (got: {len(wbs_rows)})"),
        (len(sequenced_rows) > 0, f"Must have at least 1 sequenced row (got: {len(sequenced_rows)})"),
        (
            len(sequenced_rows) == len(wbs_rows),
            f"Sequenced rows ({len(sequenced_rows)}) must match WBS rows ({len(wbs_rows)})",
        ),
        (
            abs(total_hours - expected_hours) < 1.0,
            f"Total WBS hours ({total_hours}h) must match S3 task extraction ({expected_hours}h) within 1h",
        ),
        (
            len(sprint_groups) > 0,
            f"Must have at least 1 sprint assignment (got: {len(sprint_groups)})",
        ),
        (
            all(row.get("feature") for row in wbs_rows),
            "All WBS rows must have 'feature' field",
        ),
        (
            all(row.get("hours") is not None for row in wbs_rows),
            "All WBS rows must have 'hours' field",
        ),
        (
            all(row.get("sprint_number") is not None for row in sequenced_rows),
            "All sequenced rows must have 'sprint_number' field",
        ),
    ]

    all_passed = True
    for passed, message in validations:
        if passed:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")
            all_passed = False

    if not all_passed:
        print("\n✗ SOME VALIDATIONS FAILED")
        return False

    return True


def generate_summary():
    """Generate test summary"""
    print_header("SUMMARY")

    s3_run = results.get("s3_run", {})
    s3_task_ext = results.get("s3_task_extraction", {})
    s4_result = results.get("s4_result", {})
    sprint_config = results.get("sprint_config", {})

    print(f"S3 Run ID: {s3_run.get('run_id')}")
    print("S3 Task Extraction:")
    print(f"  - Activities: {len(s3_task_ext.get('activities', []))}")
    print(f"  - Total Hours: {s3_task_ext.get('total_net_hours')}h")
    print(f"  - Verification: {'PASSED' if s3_task_ext.get('verification_passed') else 'FAILED'}")

    print(f"\nS4 Run ID: {results.get('s4_run_id')}")
    print("S4 Sprint Configuration:")
    print(f"  - Sprint Count: {sprint_config.get('sprint_count')}")
    print(f"  - Sprint Length: {sprint_config.get('sprint_length_weeks')} weeks")

    print("\nS4 Results:")
    print(f"  - WBS Rows: {len(s4_result.get('wbs_rows', []))}")
    print(f"  - Sequenced Rows: {len(s4_result.get('sequenced_rows', []))}")
    print(f"  - Total Hours: {s4_result.get('metadata', {}).get('total_hours')}h")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_dir = Path(__file__).parent.resolve()
    filename = f"{file_dir}/s3_to_s4_test_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✓ Full results saved to: {filename}")

    print("\n✅ ALL VALIDATIONS PASSED - S3 → S4 FLOW WORKING CORRECTLY!")


def main():
    """Main test execution"""
    try:
        # Authenticate
        if not authenticate():
            print("\n✗ Authentication failed, cannot continue")
            sys.exit(1)

        # Step 1: Verify S3 complete (timeline + task decomposition)
        s3_run_id = verify_s3_complete()
        if not s3_run_id:
            sys.exit(1)

        # Step 2: Load S3 → S4
        if not load_s3_to_s4():
            sys.exit(1)

        # Step 3: Set sprint params
        if not set_sprint_params():
            sys.exit(1)

        # Step 4: Trigger S4 run
        s4_run_id = trigger_s4_run()
        if not s4_run_id:
            sys.exit(1)

        # Step 5: Wait for S4 completion
        if not wait_for_s4_completion():
            print("\n⚠️  S4 run did not complete - partial test results")
            sys.exit(1)

        # Step 6: Verify WBS grouping
        if not verify_wbs_grouping():
            sys.exit(1)

        # Generate summary
        generate_summary()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
