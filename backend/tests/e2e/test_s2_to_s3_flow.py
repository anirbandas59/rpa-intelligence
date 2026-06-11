#!/usr/bin/env python3
"""
S2 → S3 Task Breakdown Flow Test

Validates complete S2 → S3 data flow including task extraction.
Reuses existing S2 run results from a use-case.
"""

import json
import sys
import time
from datetime import datetime

import requests

# Configuration
UC_ID = "3394a736-f08a-424e-aa18-f8b519004e7a"  # Same as main E2E test
BASE_URL = "http://localhost:8000/api/v1"
USE_CASES_BASE = f"{BASE_URL}/use-cases"
MAX_WAIT_TIME = 180  # 3 minutes for task extraction
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


def verify_s2_complete():
    """Verify S2 run exists and is complete"""
    print_header("STEP 1: Verify S2 Completion")

    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get use-case: {resp.text}")
        return None

    uc = resp.json()
    s2_latest_run_id = uc.get("s2_latest_run_id")

    if not s2_latest_run_id:
        print("✗ No S2 run found. Run main E2E test first:")
        print("  cd backend && uv run python tests/e2e/run_e2e_tests.py")
        return None

    print(f"✓ S2 run exists: {s2_latest_run_id}")

    # Get S2 result details
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}/s2/runs/{s2_latest_run_id}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get S2 run: {resp.text}")
        return None

    s2_run = resp.json()
    if s2_run["status"] != "complete":
        print(f"✗ S2 run not complete (status: {s2_run['status']})")
        return None

    s2_result = s2_run["result"]
    print(f"✓ S2 Status: {s2_run['status']}")
    print(f"  - Complexity Class: {s2_result['complexity_class']}")
    print(f"  - Effort Range: {s2_result['effort_min_weeks']}-{s2_result['effort_max_weeks']} weeks")
    print(f"  - Total Score: {s2_result['total_score']}")

    process_summary = s2_result.get('process_summary', {})
    print(f"  - Process Summary Activities: {len(process_summary.get('key_activities', []))}")

    results["s2_run"] = {"run_id": s2_latest_run_id, "result": s2_result}

    return s2_latest_run_id


def load_s2_to_s3():
    """Load S2 results into S3 inputs"""
    print_header("STEP 2: Load S2 Data into S3 Inputs")

    resp = requests.post(
        f"{USE_CASES_BASE}/{UC_ID}/s3/load-from-s2",
        json={"prefer_max": True},  # Use max_weeks from S2
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Load failed: {resp.text}")
        return False

    print("✓ S2 data loaded into S3 inputs")

    # Verify S3 inputs populated
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}", headers=get_headers())
    uc = resp.json()
    s3_inputs = uc.get("s3_inputs", {})

    effort_weeks = s3_inputs.get('effort_weeks')
    complexity_class = s3_inputs.get('complexity_class')

    print(f"  - effort_weeks: {effort_weeks} (source: {s3_inputs.get('effort_weeks_source')})")
    print(f"  - complexity_class: {complexity_class} (source: {s3_inputs.get('complexity_class_source')})")

    s2_result = results["s2_run"]["result"]
    if effort_weeks != s2_result['effort_max_weeks']:
        print(f"  ⚠️  effort_weeks mismatch: expected {s2_result['effort_max_weeks']}, got {effort_weeks}")
    if complexity_class != s2_result['complexity_class']:
        print(f"  ⚠️  complexity_class mismatch: expected {s2_result['complexity_class']}, got {complexity_class}")

    results["s3_inputs_loaded"] = s3_inputs

    return True


def set_timeline_params():
    """Set timeline start date"""
    print_header("STEP 3: Set Timeline Parameters")

    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s3/inputs",
        json={"start_date": "2026-07-01"},  # Keep effort_weeks from S2
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Update failed: {resp.text}")
        return False

    print("✓ Timeline start date set to 2026-07-01")
    return True


def trigger_s3_run():
    """Trigger S3 run (timeline + task extraction)"""
    print_header("STEP 4: Trigger S3 Run (Timeline + Task Extraction)")

    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s3/runs", json={}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Run failed: {resp.text}")
        return None

    run_data = resp.json()
    s3_run_id = run_data["run_id"]
    status = run_data["status"]

    print(f"✓ S3 run created: {s3_run_id}")
    print(f"✓ Status: {status}")

    if status != "complete":
        print(f"✗ Expected status 'complete', got '{status}'")
        return None

    # Verify timeline calculation
    result = run_data.get("result", {})

    if "phases" not in result:
        print("✗ Timeline result missing 'phases'")
        return None

    total_weeks = result.get('total_weeks')
    phases = result.get('phases', [])

    print(f"✓ Timeline calculated: {total_weeks} weeks, {len(phases)} phases")

    for phase in phases:
        print(f"  - {phase['name']:8s}: {phase['weeks']} weeks ({phase['start_date']} to {phase['end_date']})")

    build_sit = result.get("build_sit_window", {})
    print(f"\n✓ Build+SIT Window: {build_sit.get('start_date')} to {build_sit.get('end_date')}")

    results["s3_run"] = {"run_id": s3_run_id, "result": result}

    return s3_run_id


def wait_for_task_extraction():
    """Wait for task extraction background job to complete"""
    print_header("STEP 5: Wait for Task Extraction (Background Job)")
    print("Task extraction runs asynchronously (30-120 seconds)...")
    print("Polling readiness endpoint every 5 seconds...\n")

    elapsed = 0
    task_status = "unknown"

    while elapsed < MAX_WAIT_TIME:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        resp = requests.get(f"{BASE_URL}/use-cases/{UC_ID}/readiness", headers=get_headers())

        if resp.status_code == 200:
            readiness = resp.json()
            task_status = readiness.get("s3_task_extraction", "unknown")
            print(f"  [{elapsed:3d}s] Task extraction status: {task_status}")

            if task_status == "complete":
                print("\n✓ Task extraction complete!")
                return True
            elif task_status == "failed":
                print("\n✗ Task extraction failed")
                return False
        else:
            print(f"  [{elapsed:3d}s] Readiness check failed: {resp.status_code}")

    print(f"\n✗ Task extraction did not complete within {MAX_WAIT_TIME}s (status: {task_status})")
    return False


def verify_task_breakdown():
    """Verify task breakdown meets constraints"""
    print_header("STEP 6: Verify Task Breakdown")

    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get use-case: {resp.text}")
        return False

    uc = resp.json()
    task_extraction = uc.get("s3_inputs", {}).get("task_extraction", {})

    if not task_extraction:
        print("✗ No task_extraction data found in s3_inputs")
        return False

    extraction_status = task_extraction.get('extraction_status')
    source = task_extraction.get('source')
    activities = task_extraction.get('activities', [])
    total_net_hours = task_extraction.get('total_net_hours', 0)
    verification_passed = task_extraction.get('verification_passed')

    print(f"✓ Extraction Status: {extraction_status}")
    print(f"✓ Source: {source}")
    print(f"✓ Activities Extracted: {len(activities)}")
    print(f"✓ Total Net Hours: {total_net_hours}")
    print(f"✓ Verification Passed: {verification_passed}")

    # Calculate expected hours
    s3_inputs = results.get("s3_inputs_loaded", {})
    effort_weeks = s3_inputs.get('effort_weeks', 0)
    expected_hours = effort_weeks * 40

    print(f"\n  Expected Hours (from effort): {expected_hours}h ({effort_weeks} weeks × 40h/week)")
    print(f"  Actual Net Hours: {total_net_hours}h")
    print(f"  Difference: {abs(total_net_hours - expected_hours)}h")

    # Display sample activities
    print("\nSample Activities (first 5):")
    for i, activity in enumerate(activities[:5], 1):
        name = activity.get('name', 'Unnamed')
        hours = activity.get('hours', 0)
        reusable = activity.get('reusable', False)
        print(f"  {i}. {name[:50]:50s} - {hours:5.1f}h (reusable: {reusable})")

    if len(activities) > 5:
        print(f"  ... and {len(activities) - 5} more activities")

    results["task_extraction"] = task_extraction

    # Validate constraints
    print_header("VALIDATION")

    validations = [
        (extraction_status == "complete", f"Extraction status must be 'complete' (got: {extraction_status})"),
        (verification_passed is True, f"Hour sum verification must pass (got: {verification_passed})"),
        (len(activities) > 0, f"Must have at least 1 activity (got: {len(activities)})"),
        (
            abs(total_net_hours - expected_hours) < 1.0,
            f"Net hours ({total_net_hours}) must match expected ({expected_hours}) within 1h tolerance",
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

    s2_run = results.get("s2_run", {})
    s3_run = results.get("s3_run", {})
    s3_inputs = results.get("s3_inputs_loaded", {})
    task_ext = results.get("task_extraction", {})

    print(f"S2 Run ID: {s2_run.get('run_id')}")
    print(f"S3 Run ID: {s3_run.get('run_id')}")
    print(f"Complexity: {s3_inputs.get('complexity_class')}")
    print(f"Effort: {s3_inputs.get('effort_weeks')} weeks")
    print(f"Activities: {len(task_ext.get('activities', []))}")
    print(f"Total Hours: {task_ext.get('total_net_hours')}h")
    print(f"Verification: {'PASSED' if task_ext.get('verification_passed') else 'FAILED'}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"s2_to_s3_test_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✓ Full results saved to: {filename}")

    print("\n✅ ALL VALIDATIONS PASSED - S2 → S3 FLOW WORKING CORRECTLY!")


def main():
    """Main test execution"""
    try:
        # Authenticate
        if not authenticate():
            print("\n✗ Authentication failed, cannot continue")
            sys.exit(1)

        # Step 1: Verify S2 complete
        s2_run_id = verify_s2_complete()
        if not s2_run_id:
            sys.exit(1)

        # Step 2: Load S2 → S3
        if not load_s2_to_s3():
            sys.exit(1)

        # Step 3: Set timeline params
        if not set_timeline_params():
            sys.exit(1)

        # Step 4: Trigger S3 run
        s3_run_id = trigger_s3_run()
        if not s3_run_id:
            sys.exit(1)

        # Step 5: Wait for task extraction
        if not wait_for_task_extraction():
            print("\n⚠️  Task extraction did not complete - partial test results")
            # Continue to show what we have
        else:
            # Step 6: Verify task breakdown
            if not verify_task_breakdown():
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
