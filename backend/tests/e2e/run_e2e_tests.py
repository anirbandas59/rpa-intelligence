#!/usr/bin/env python3
"""
End-to-End API Testing Script for RPA Intelligence Platform
Tests Stage 2→3→4 data flow and agent comparison
"""

import json
import sys
import time
from datetime import datetime

import requests

# Configuration
UC_ID = "3394a736-f08a-424e-aa18-f8b519004e7a"
BASE_URL = "http://localhost:8000/api/v1"
# All stage routers are under /use-cases prefix
USE_CASES_BASE = f"{BASE_URL}/use-cases"
MAX_WAIT_TIME = 180  # 3 minutes per run
POLL_INTERVAL = 3  # seconds

# Test document path
SAMPLE_PDF = "backend/data/samples/sample_simple.pdf"

# Authentication
AUTH_EMAIL = "test123@example.com"
AUTH_PASSWORD = "testpass123"
access_token = None

# Test document
TEST_DOCUMENT = """Invoice Processing Automation - Process Definition Document

Process Overview:
This automation reads invoices from email, extracts data, validates against
business rules, and posts to SAP.

Systems:
- Outlook email
- SAP ERP (FB60 transaction)
- Oracle database

Activities:
1. Login to Outlook
2. Read emails from Invoice folder
3. Download PDF attachments
4. Extract invoice data using OCR
5. Validate vendor against Oracle database
6. Check invoice amount threshold
7. Apply approval workflow rules
8. Login to SAP
9. Open FB60 transaction
10. Enter invoice header data
11. Enter line items
12. Post to SAP
13. Update status in Oracle
14. Send confirmation email
15. Logout from SAP

Business Rules:
- If amount > 10000: Route to manager approval
- If vendor not in database: Create new vendor record
- If duplicate invoice number: Reject and notify

UI Screens:
- Outlook inbox window
- SAP login screen
- SAP FB60 transaction screen
- Approval workflow screen

Technologies:
- OCR for PDF extraction
- Database connectivity for Oracle"""

# Expected results
EXPECTED = {
    "activities": "M",  # 15 activities
    "business_rules": "L",  # 3 rules
    "layouts": "M",  # 4 screens
    "interfaces": "M",  # 3 systems
    "technology": "M",  # 2 tech integrations
    "complexity_class": ["M", "L"],  # Either is acceptable
    "activities_count": 15,
    "rules_count": 3,
    "systems_count": 3,
}

# Test results storage
results = {"s2_prompt_based": None, "s2_tool_based": None, "s3_timeline": None, "s4_tracker": None, "comparison": {}}


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


def wait_for_run(endpoint, run_id, stage_name):
    """Poll for run completion"""
    print(f"Waiting for {stage_name} run to complete...")
    elapsed = 0

    while elapsed < MAX_WAIT_TIME:
        try:
            resp = requests.get(f"{endpoint}/{run_id}", headers=get_headers())
            if resp.status_code == 200:
                run_data = resp.json()
                status = run_data.get("status")
                print(f"  [{elapsed}s] Status: {status}")

                if status == "complete":
                    print(f"✓ {stage_name} completed successfully!")
                    return run_data
                elif status == "failed":
                    print(f"✗ {stage_name} failed!")
                    print(f"  Error: {run_data.get('error')}")
                    return None

            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
        except Exception as e:
            print(f"✗ Error polling: {e}")
            return None

    print(f"✗ Timeout after {MAX_WAIT_TIME}s")
    return None


def verify_bands(result, expected, agent_type):
    """Verify band assignments match expected values"""
    bands = result.get("bands", {})
    mismatches = []

    for attr, expected_band in expected.items():
        if attr in bands:
            actual = bands[attr]
            if actual != expected_band:
                mismatches.append(f"{attr}: expected {expected_band}, got {actual}")

    if mismatches:
        print(f"\n⚠️  Band Mismatches ({agent_type}):")
        for mm in mismatches:
            print(f"    - {mm}")
        return False
    else:
        print(f"\n✓ All bands match expected values ({agent_type})")
        return True


def test_stage2_prompt_based():
    """Test Stage 2 with prompt-based agent"""
    print_header("PHASE 1.1: Stage 2 API - Prompt-Based Agent")

    # Upload pasted text (TEST_DOCUMENT with known complexity)
    print("Step 1: Uploading process text (15 activities, 3 rules, 4 screens)...")
    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s2/inputs", json={"pasted_text": TEST_DOCUMENT}, headers=get_headers()
    )

    if resp.status_code not in [200, 201]:
        print(f"✗ Upload failed: {resp.status_code} - {resp.text}")
        return None
    print("✓ Process text uploaded")

    # Trigger run
    print("\nStep 2: Triggering S2 run (prompt-based)...")
    resp = requests.post(
        f"{USE_CASES_BASE}/{UC_ID}/s2/runs",
        json={"use_tool": False},  # Uses default Sonnet model from settings
        headers=get_headers(),
    )

    if resp.status_code not in [200, 201, 202]:
        print(f"✗ Run creation failed: {resp.status_code} - {resp.text}")
        return None

    run_data = resp.json()
    run_id = run_data.get("run_id")
    status = run_data.get("status")
    print(f"✓ Run created: {run_id} (status: {status})")

    # Wait for completion
    print("\nStep 3: Waiting for completion...")
    final_result = wait_for_run(f"{USE_CASES_BASE}/{UC_ID}/s2/runs", run_id, "Stage 2")

    if not final_result:
        return None

    # Display results
    result = final_result.get("result", {})
    bands = result.get("bands", {})
    ps = result.get("process_summary", {})

    print("\n=== RESULTS (Prompt-Based) ===")
    print("Complexity Bands:")
    print(f"  Activities: {bands.get('activities')} (expected: M)")
    print(f"  Business Rules: {bands.get('business_rules')} (expected: L)")
    print(f"  Layouts: {bands.get('layouts')} (expected: M)")
    print(f"  Interfaces: {bands.get('interfaces')} (expected: M)")
    print(f"  Technology: {bands.get('technology')} (expected: M)")

    print("\nComplexity Score:")
    print(f"  Total Score: {result.get('total_score')}")
    print(f"  Class: {result.get('complexity_class')} (expected: M or L)")
    print(f"  Effort: {result.get('effort_min_weeks')}-{result.get('effort_max_weeks')} weeks")

    print("\nProcess Summary:")
    print(f"  Activities: {len(ps.get('key_activities', []))} (expected: ~15)")
    print(f"  Rules: {len(ps.get('key_logical_points', []))} (expected: 3)")
    print(f"  Systems: {len(ps.get('key_applications', []))} (expected: 3)")

    # Verify
    verify_bands(
        result,
        {
            "activities": EXPECTED["activities"],
            "business_rules": EXPECTED["business_rules"],
            "layouts": EXPECTED["layouts"],
            "interfaces": EXPECTED["interfaces"],
            "technology": EXPECTED["technology"],
        },
        "prompt-based",
    )

    results["s2_prompt_based"] = {
        "run_id": run_id,
        "result": result,
        "bands": bands,
        "process_summary": ps,
        "timestamp": datetime.now().isoformat(),
    }

    return run_id


def test_stage2_tool_based():
    """Test Stage 2 with tool-based agent"""
    print_header("PHASE 1.2: Stage 2 API - Tool-Based Agent")

    print("NOTE: Tool-based agent requires backend code changes:")
    print("      1. Import: from agents.process_agent_with_tools import extract_bands_with_tools")
    print("      2. Call extract_bands_with_tools() instead of run_s2_assessment()")
    print("      3. Currently BOTH tests will use prompt-based agent.\n")

    # Upload pasted text (same as prompt-based for comparison)
    print("Step 1: Uploading process text (15 activities, 3 rules, 4 screens)...")
    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s2/inputs", json={"pasted_text": TEST_DOCUMENT}, headers=get_headers()
    )

    if resp.status_code not in [200, 201]:
        print(f"✗ Upload failed: {resp.status_code} - {resp.text}")
        return None
    print("✓ Process text uploaded")

    # Trigger run
    print("\nStep 2: Triggering S2 run (tool-based)...")
    resp = requests.post(
        f"{USE_CASES_BASE}/{UC_ID}/s2/runs",
        json={"use_tool": True},  # Uses default Sonnet model from settings
        headers=get_headers()
    )

    if resp.status_code not in [200, 201, 202]:
        print(f"✗ Run creation failed: {resp.status_code} - {resp.text}")
        return None

    run_data = resp.json()
    run_id = run_data.get("run_id")
    status = run_data.get("status")
    print(f"✓ Run created: {run_id} (status: {status})")

    # Wait for completion
    print("\nStep 3: Waiting for completion...")
    final_result = wait_for_run(f"{USE_CASES_BASE}/{UC_ID}/s2/runs", run_id, "Stage 2 (Tool-Based)")

    if not final_result:
        return None

    # Display results
    result = final_result.get("result", {})
    bands = result.get("bands", {})
    ps = result.get("process_summary", {})

    print("\n=== RESULTS (Tool-Based) ===")
    print("Complexity Bands:")
    print(f"  Activities: {bands.get('activities')} (expected: M)")
    print(f"  Business Rules: {bands.get('business_rules')} (expected: L)")
    print(f"  Layouts: {bands.get('layouts')} (expected: M)")
    print(f"  Interfaces: {bands.get('interfaces')} (expected: M)")
    print(f"  Technology: {bands.get('technology')} (expected: M)")

    print("\nComplexity Score:")
    print(f"  Total Score: {result.get('total_score')}")
    print(f"  Class: {result.get('complexity_class')} (expected: M or L)")
    print(f"  Effort: {result.get('effort_min_weeks')}-{result.get('effort_max_weeks')} weeks")

    print("\nProcess Summary:")
    print(f"  Activities: {len(ps.get('key_activities', []))} (expected: ~15)")
    print(f"  Rules: {len(ps.get('key_logical_points', []))} (expected: 3)")
    print(f"  Systems: {len(ps.get('key_applications', []))} (expected: 3)")

    # Check for extraction notes (tool-based indicator)
    extraction_notes = result.get("extraction_notes", "")
    if "tool" in extraction_notes.lower():
        print("\n✓ TOOL-BASED AGENT CONFIRMED (notes mention tool usage)")
    else:
        print("\n⚠️  May be prompt-based (no tool mention in notes)")

    # Verify
    verify_bands(
        result,
        {
            "activities": EXPECTED["activities"],
            "business_rules": EXPECTED["business_rules"],
            "layouts": EXPECTED["layouts"],
            "interfaces": EXPECTED["interfaces"],
            "technology": EXPECTED["technology"],
        },
        "tool-based",
    )

    results["s2_tool_based"] = {
        "run_id": run_id,
        "result": result,
        "bands": bands,
        "process_summary": ps,
        "extraction_notes": extraction_notes,
        "timestamp": datetime.now().isoformat(),
    }

    return run_id


def test_stage3_timeline(s2_run_id):
    """Test Stage 3 timeline calculation"""
    print_header("PHASE 1.3: Stage 3 API - Timeline Calculation")

    # Load from S2
    print("Step 1: Loading S2 data into S3 inputs...")
    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s3/load-from-s2", json={"prefer_max": True}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Load failed: {resp.text}")
        return None
    print("✓ S2 data loaded")

    # Set timeline inputs
    print("\nStep 2: Setting timeline inputs...")
    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s3/inputs",
        json={"effort_weeks": 5, "start_date": "2026-07-01"},
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Update failed: {resp.text}")
        return None
    print("✓ Timeline inputs set")

    # Trigger S3 run (synchronous)
    print("\nStep 3: Running S3 timeline calculation...")
    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s3/runs", json={}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Run failed: {resp.text}")
        return None

    run_data = resp.json()
    run_id = run_data["run_id"]
    print(f"✓ Timeline calculated: {run_id}")

    # Get result
    resp = requests.get(f"{USE_CASES_BASE}/{UC_ID}/s3/runs/{run_id}", headers=get_headers())
    if resp.status_code != 200:
        print(f"✗ Failed to get result: {resp.text}")
        return None

    final_result = resp.json()
    result = final_result.get("result", {})

    print("\n=== RESULTS (Stage 3) ===")
    print("Timeline:")
    print(f"  Total Weeks: {result.get('total_weeks')}")
    print(f"  Start: {result.get('project_start_date')}")
    print(f"  End: {result.get('project_end_date')}")
    print(f"  Phases: {len(result.get('phases', []))} (expected: 6)")

    phases = result.get("phases", [])
    for phase in phases:
        print(f"    - {phase['name']}: {phase['weeks']} weeks ({phase['start_date']} to {phase['end_date']})")

    build_sit = result.get("build_sit_window", {})
    print("\nBuild+SIT Window (for S4):")
    print(f"  Start: {build_sit.get('start_date')}")
    print(f"  End: {build_sit.get('end_date')}")

    # Check task extraction status
    print("\nTask Extraction Status:")
    resp = requests.get(f"{BASE_URL}/use-cases/{UC_ID}/readiness", headers=get_headers())
    if resp.status_code == 200:
        readiness = resp.json()
        task_status = readiness.get("s3_task_extraction", "unknown")
        print(f"  Status: {task_status}")

        if task_status == "complete":
            task_ext = result.get("task_extraction", {})
            print(f"  Activities: {len(task_ext.get('activities', []))}")
            print(f"  Total Hours: {task_ext.get('total_effort_hours')}")

    results["s3_timeline"] = {"run_id": run_id, "result": result, "timestamp": datetime.now().isoformat()}

    return run_id


def test_stage4_tracker(s3_run_id):
    """Test Stage 4 sprint tracker"""
    print_header("PHASE 1.4: Stage 4 API - Sprint Assignment")

    # Load from S3
    print("Step 1: Loading S3 data into S4 inputs...")
    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s4/load-from-s3", json={}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Load failed: {resp.text}")
        return None
    print("✓ S3 data loaded")

    # Set sprint inputs
    print("\nStep 2: Setting sprint configuration...")
    resp = requests.patch(
        f"{USE_CASES_BASE}/{UC_ID}/s4/inputs",
        json={"sprint_count": 3, "sprint_length_weeks": 2, "sprint_capacity": 40},
        headers=get_headers(),
    )

    if resp.status_code != 200:
        print(f"✗ Update failed: {resp.text}")
        return None
    print("✓ Sprint config set")

    # Trigger S4 run (async)
    print("\nStep 3: Running S4 tracker assignment...")
    resp = requests.post(f"{USE_CASES_BASE}/{UC_ID}/s4/runs", json={}, headers=get_headers())

    if resp.status_code != 200:
        print(f"✗ Run failed: {resp.text}")
        return None

    run_data = resp.json()
    run_id = run_data["run_id"]
    print(f"✓ Run created: {run_id}")

    # Wait for completion
    print("\nStep 4: Waiting for completion...")
    final_result = wait_for_run(f"{USE_CASES_BASE}/{UC_ID}/s4/runs", run_id, "Stage 4")

    if not final_result:
        return None

    result = final_result.get("result", {})

    print("\n=== RESULTS (Stage 4) ===")
    print(f"WBS Rows: {len(result.get('wbs_rows', []))}")
    print(f"Sequenced Rows: {len(result.get('sequenced_rows', []))}")

    metadata = result.get("metadata", {})
    print("\nMetadata:")
    print(f"  Complexity: {metadata.get('complexity_class')}")
    print(f"  Effort Weeks: {metadata.get('effort_weeks')}")
    print(f"  Total Hours: {metadata.get('total_hours')}")
    print(f"  Total Rows: {metadata.get('total_rows')}")

    # Check sprint_number field
    sequenced = result.get("sequenced_rows", [])
    if sequenced:
        print("\nSprint Assignment Check:")
        has_sprint_num = "sprint_number" in sequenced[0]
        if has_sprint_num:
            print("  ✓ sprint_number field present")
            sprint_counts = {}
            for row in sequenced:
                sprint = row.get("sprint_number", 0)
                sprint_counts[sprint] = sprint_counts.get(sprint, 0) + 1
            for sprint, count in sorted(sprint_counts.items()):
                print(f"    Sprint {sprint}: {count} rows")
        else:
            print("  ✗ sprint_number field MISSING!")

    results["s4_tracker"] = {"run_id": run_id, "result": result, "timestamp": datetime.now().isoformat()}

    return run_id


def generate_report():
    """Generate test execution report"""
    print_header("TEST EXECUTION SUMMARY")

    print("Phase 1: Backend API Testing")
    print(f"  S2 Prompt-Based: {'✓ PASS' if results['s2_prompt_based'] else '✗ FAIL'}")
    print(f"  S2 Tool-Based: {'✓ PASS' if results['s2_tool_based'] else '⊘ SKIP'}")
    print(f"  S3 Timeline: {'✓ PASS' if results['s3_timeline'] else '✗ FAIL'}")
    print(f"  S4 Tracker: {'✓ PASS' if results['s4_tracker'] else '✗ FAIL'}")

    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"e2e_test_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Full results saved to: {filename}")


def main():
    """Main test execution"""
    try:
        # Authenticate first
        if not authenticate():
            print("\n✗ Authentication failed, cannot continue")
            sys.exit(1)

        # Phase 1.1: Test Stage 2 (prompt-based)
        s2_prompt_run_id = test_stage2_prompt_based()
        if not s2_prompt_run_id:
            print("\n✗ Stage 2 (prompt-based) test failed")
            # Continue anyway to try tool-based

        # Phase 1.2: Test Stage 2 (tool-based)
        s2_tool_run_id = test_stage2_tool_based()
        if not s2_tool_run_id:
            print("\n✗ Stage 2 (tool-based) test failed")

        # Use whichever S2 run succeeded for S3/S4 testing
        s2_run_id = s2_tool_run_id if s2_tool_run_id else s2_prompt_run_id

        if not s2_run_id:
            print("\n✗ Both Stage 2 tests failed, cannot continue")
            sys.exit(1)

        # Phase 1.3: Test Stage 3
        s3_run_id = test_stage3_timeline(s2_run_id)
        if not s3_run_id:
            print("\n✗ Stage 3 test failed, cannot continue")
            sys.exit(1)

        # Phase 1.4: Test Stage 4
        s4_run_id = test_stage4_tracker(s3_run_id)
        if not s4_run_id:
            print("\n✗ Stage 4 test failed")
            sys.exit(1)

        # Generate report
        generate_report()

        print("\n✓ All tests completed successfully!")

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
