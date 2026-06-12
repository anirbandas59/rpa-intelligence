"""
Phase 4: Data Flow Validation Tests
Verifies cross-stage data contracts per CLAUDE.md specifications.
"""

import pytest
import httpx
from typing import Dict, Any, Optional
import json


class DataFlowValidator:
    """Validates data flows between stages S2→S3→S4"""

    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def get_s2_result(self, use_case_id: str, run_id: str) -> Dict[str, Any]:
        """Fetch S2 run result"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/use-cases/{use_case_id}/s2/runs/{run_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def get_s3_inputs(self, use_case_id: str) -> Dict[str, Any]:
        """Fetch S3 inputs from use-case"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/use-cases/{use_case_id}",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get("s3_inputs", {})

    async def get_s3_result(self, use_case_id: str, run_id: str) -> Dict[str, Any]:
        """Fetch S3 run result"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/use-cases/{use_case_id}/s3/runs/{run_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def get_s4_inputs(self, use_case_id: str) -> Dict[str, Any]:
        """Fetch S4 inputs from use-case"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/use-cases/{use_case_id}",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get("s4_inputs", {})

    async def get_s4_result(self, use_case_id: str, run_id: str) -> Dict[str, Any]:
        """Fetch S4 run result"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/use-cases/{use_case_id}/s4/runs/{run_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    def validate_s2_to_s3_flow(
        self,
        s2_result: Dict[str, Any],
        s3_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate S2→S3 data flow contract.

        Expected transfers:
        - complexity_class
        - effort_weeks (from effort_max_weeks or effort_min_weeks)
        - process_summary (passed to task extraction agent)
        """
        validation_results = {
            "complexity_class_match": False,
            "effort_weeks_match": False,
            "process_summary_present": False,
            "source_tags_correct": False,
            "errors": []
        }

        # Extract S2 outputs
        s2_complexity = s2_result.get("result", {}).get("complexity_class")
        s2_effort_max = s2_result.get("result", {}).get("effort_max_weeks")
        s2_effort_min = s2_result.get("result", {}).get("effort_min_weeks")
        s2_process_summary = s2_result.get("result", {}).get("process_summary")

        # Check S3 inputs
        s3_complexity = s3_inputs.get("complexity_class")
        s3_effort_weeks = s3_inputs.get("effort_weeks")

        # Validate complexity_class transfer
        if s2_complexity == s3_complexity:
            validation_results["complexity_class_match"] = True
        else:
            validation_results["errors"].append(
                f"Complexity class mismatch: S2={s2_complexity}, S3={s3_complexity}"
            )

        # Validate effort_weeks transfer (should be max or min from S2)
        if s3_effort_weeks == s2_effort_max or s3_effort_weeks == s2_effort_min:
            validation_results["effort_weeks_match"] = True
        else:
            validation_results["errors"].append(
                f"Effort weeks mismatch: S2_max={s2_effort_max}, S2_min={s2_effort_min}, S3={s3_effort_weeks}"
            )

        # Validate process_summary is present in S2 result (will be passed to S3 task extraction)
        if s2_process_summary and isinstance(s2_process_summary, dict):
            validation_results["process_summary_present"] = True

            # Check required fields
            required_fields = ["key_activities", "key_logical_points", "key_applications"]
            missing_fields = [f for f in required_fields if f not in s2_process_summary]
            if missing_fields:
                validation_results["errors"].append(
                    f"Process summary missing fields: {missing_fields}"
                )
        else:
            validation_results["errors"].append("Process summary not present in S2 result")

        # Check source tags (if available in S3 inputs)
        # Note: Source tags might be at field level or in metadata
        s3_metadata = s3_inputs.get("_metadata", {})
        if s3_metadata.get("_source") == "from_s2":
            validation_results["source_tags_correct"] = True

        validation_results["passed"] = (
            validation_results["complexity_class_match"] and
            validation_results["effort_weeks_match"] and
            validation_results["process_summary_present"]
        )

        return validation_results

    def validate_s3_to_s4_flow(
        self,
        s3_result: Dict[str, Any],
        s4_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate S3→S4 data flow contract.

        Expected transfers:
        - build_sit_window (start_date, end_date)
        - task_extraction (activities, steps)
        - sprint_count (derived from timeline)
        """
        validation_results = {
            "build_sit_window_match": False,
            "task_extraction_present": False,
            "sprint_count_match": False,
            "source_tags_correct": False,
            "errors": []
        }

        # Extract S3 outputs
        s3_build_sit = s3_result.get("result", {}).get("build_sit_window")
        s3_task_extraction = s3_result.get("result", {}).get("task_extraction")

        # Check S4 inputs
        s4_build_sit = s4_inputs.get("build_sit_window")

        # Validate build_sit_window transfer
        if s3_build_sit and s4_build_sit:
            if (s3_build_sit.get("start_date") == s4_build_sit.get("start_date") and
                s3_build_sit.get("end_date") == s4_build_sit.get("end_date")):
                validation_results["build_sit_window_match"] = True
            else:
                validation_results["errors"].append(
                    f"Build/SIT window mismatch: S3={s3_build_sit}, S4={s4_build_sit}"
                )
        else:
            validation_results["errors"].append("Build/SIT window missing in S3 or S4")

        # Validate task_extraction is present in S3 result
        # Note: task_extraction is passed to S4 tracker agent, not stored in s4_inputs
        if s3_task_extraction and isinstance(s3_task_extraction, dict):
            validation_results["task_extraction_present"] = True

            # Check required fields
            if "activities" not in s3_task_extraction:
                validation_results["errors"].append("Task extraction missing activities field")
        else:
            validation_results["errors"].append("Task extraction not present in S3 result")

        # Sprint count validation (if available)
        s3_sprint_count = s3_result.get("result", {}).get("sprint_count")
        s4_sprint_count = s4_inputs.get("sprint_count")
        if s3_sprint_count and s4_sprint_count:
            if s3_sprint_count == s4_sprint_count:
                validation_results["sprint_count_match"] = True
            else:
                validation_results["errors"].append(
                    f"Sprint count mismatch: S3={s3_sprint_count}, S4={s4_sprint_count}"
                )

        validation_results["passed"] = (
            validation_results["build_sit_window_match"] and
            validation_results["task_extraction_present"]
        )

        return validation_results

    def validate_task_extraction_alignment(
        self,
        s2_result: Dict[str, Any],
        s3_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Critical validation: S3 task extraction must align with S2 process summary.

        Per CLAUDE.md Phase 1.4 fix:
        - S3 activities are breakdowns of S2 activities
        - S3 can add login/logout for systems mentioned in S2
        - S3 must NOT create entirely new process flows
        - S3 activities should reference S2 technologies/applications
        """
        validation_results = {
            "activities_aligned": False,
            "systems_referenced": False,
            "no_new_flows": True,
            "alignment_score": 0.0,
            "errors": [],
            "warnings": []
        }

        # Extract S2 process summary
        s2_summary = s2_result.get("result", {}).get("process_summary", {})
        s2_activities = s2_summary.get("key_activities", [])
        s2_applications = s2_summary.get("key_applications", [])

        # Extract S3 task extraction
        s3_extraction = s3_result.get("result", {}).get("task_extraction", {})
        s3_activities = s3_extraction.get("activities", [])

        if not s2_activities:
            validation_results["errors"].append("S2 has no key_activities in process_summary")
            return validation_results

        if not s3_activities:
            validation_results["errors"].append("S3 has no activities in task_extraction")
            return validation_results

        # Extract S3 activity names
        s3_activity_names = [
            act.get("activity_name", "") for act in s3_activities if isinstance(act, dict)
        ]

        # Check alignment: S3 activities should be breakdowns or mentions of S2 activities
        aligned_count = 0
        for s2_activity in s2_activities:
            s2_lower = s2_activity.lower()

            # Check if any S3 activity references this S2 activity
            for s3_name in s3_activity_names:
                s3_lower = s3_name.lower()

                # Check for keyword overlap
                s2_keywords = set(s2_lower.split())
                s3_keywords = set(s3_lower.split())
                overlap = s2_keywords & s3_keywords

                if len(overlap) >= 2:  # At least 2 words in common
                    aligned_count += 1
                    break

        # Calculate alignment score
        alignment_score = aligned_count / len(s2_activities) if s2_activities else 0.0
        validation_results["alignment_score"] = alignment_score

        if alignment_score >= 0.7:  # 70% of S2 activities referenced in S3
            validation_results["activities_aligned"] = True
        else:
            validation_results["warnings"].append(
                f"Low alignment score: {alignment_score:.2%}. "
                f"Only {aligned_count}/{len(s2_activities)} S2 activities referenced in S3"
            )

        # Check if S3 references S2 systems/applications
        if s2_applications:
            referenced_systems = 0
            for app in s2_applications:
                app_lower = app.lower()

                # Check if any S3 activity mentions this application
                for s3_name in s3_activity_names:
                    if app_lower in s3_name.lower():
                        referenced_systems += 1
                        break

            if referenced_systems > 0:
                validation_results["systems_referenced"] = True
            else:
                validation_results["warnings"].append(
                    f"None of S2 applications {s2_applications} referenced in S3 activities"
                )

        # Check for suspicious new activities (heuristic)
        # Allowed additions: login/logout, setup, error handling
        allowed_keywords = ["login", "logout", "setup", "initialize", "error", "validation"]
        suspicious_activities = []

        for s3_name in s3_activity_names:
            s3_lower = s3_name.lower()

            # Check if it's an allowed addition
            is_allowed = any(kw in s3_lower for kw in allowed_keywords)

            # Check if it references S2 content
            s3_keywords = set(s3_lower.split())
            s2_all_keywords = set()
            for s2_activity in s2_activities:
                s2_all_keywords.update(s2_activity.lower().split())

            has_s2_reference = len(s3_keywords & s2_all_keywords) >= 2

            if not is_allowed and not has_s2_reference:
                suspicious_activities.append(s3_name)

        if suspicious_activities:
            validation_results["no_new_flows"] = False
            validation_results["warnings"].append(
                f"Suspicious new activities not in S2: {suspicious_activities}"
            )

        validation_results["passed"] = (
            validation_results["activities_aligned"] and
            validation_results["no_new_flows"]
        )

        return validation_results

    def validate_hour_constraints(
        self,
        s3_result: Dict[str, Any],
        s4_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate hour constraints across S3 and S4.

        Constraints:
        - S3 task extraction: Σ(step hours where reusability != "full") = total_effort_hours
        - S4 WBS rows: Σ(row hours) = total_effort_hours
        - total_effort_hours = effort_weeks × 40
        """
        validation_results = {
            "s3_hours_valid": False,
            "s4_hours_valid": False,
            "s3_s4_hours_match": False,
            "errors": []
        }

        # Extract S3 task extraction
        s3_extraction = s3_result.get("result", {}).get("task_extraction", {})
        s3_total_effort = s3_extraction.get("total_effort_hours")
        s3_activities = s3_extraction.get("activities", [])

        # Calculate S3 step hours
        s3_calculated_hours = 0.0
        for activity in s3_activities:
            if not isinstance(activity, dict):
                continue

            steps = activity.get("steps", [])
            for step in steps:
                if not isinstance(step, dict):
                    continue

                hours = step.get("hours", 0)
                reusability = step.get("reusability", "")

                # Only count hours where reusability != "full"
                if reusability != "full":
                    s3_calculated_hours += hours

        # Validate S3 hour constraint
        if s3_total_effort:
            if abs(s3_calculated_hours - s3_total_effort) < 0.1:  # Allow small floating point error
                validation_results["s3_hours_valid"] = True
            else:
                validation_results["errors"].append(
                    f"S3 hour constraint violated: expected {s3_total_effort}, got {s3_calculated_hours}"
                )

        # Extract S4 WBS rows
        s4_wbs_rows = s4_result.get("result", {}).get("wbs_rows", [])
        s4_metadata = s4_result.get("result", {}).get("metadata", {})
        s4_total_hours = s4_metadata.get("total_hours")

        # Calculate S4 row hours
        s4_calculated_hours = 0.0
        for row in s4_wbs_rows:
            if isinstance(row, dict):
                s4_calculated_hours += row.get("hours", 0)

        # Validate S4 hour constraint
        if s4_total_hours:
            if abs(s4_calculated_hours - s4_total_hours) < 0.1:
                validation_results["s4_hours_valid"] = True
            else:
                validation_results["errors"].append(
                    f"S4 hour constraint violated: expected {s4_total_hours}, got {s4_calculated_hours}"
                )

        # Validate S3 and S4 totals match
        if s3_total_effort and s4_total_hours:
            if abs(s3_total_effort - s4_total_hours) < 0.1:
                validation_results["s3_s4_hours_match"] = True
            else:
                validation_results["errors"].append(
                    f"S3 and S4 total hours mismatch: S3={s3_total_effort}, S4={s4_total_hours}"
                )

        validation_results["passed"] = (
            validation_results["s3_hours_valid"] and
            validation_results["s4_hours_valid"] and
            validation_results["s3_s4_hours_match"]
        )

        return validation_results


@pytest.mark.asyncio
async def test_full_data_flow_validation():
    """
    Complete data flow validation test.
    Requires:
    - Backend running on localhost:8000
    - Completed S2→S3→S4 run with valid run_ids
    """
    # Test configuration (update with actual IDs from your test run)
    USE_CASE_ID = "test-uc-id"  # Replace with actual use-case ID
    S2_RUN_ID = "test-s2-run-id"  # Replace with actual S2 run ID
    S3_RUN_ID = "test-s3-run-id"  # Replace with actual S3 run ID
    S4_RUN_ID = "test-s4-run-id"  # Replace with actual S4 run ID

    # Initialize validator
    validator = DataFlowValidator()

    # Fetch all results
    print("\n" + "="*80)
    print("PHASE 4: DATA FLOW VALIDATION")
    print("="*80)

    print("\n[1/5] Fetching S2 result...")
    s2_result = await validator.get_s2_result(USE_CASE_ID, S2_RUN_ID)

    print("[2/5] Fetching S3 inputs and result...")
    s3_inputs = await validator.get_s3_inputs(USE_CASE_ID)
    s3_result = await validator.get_s3_result(USE_CASE_ID, S3_RUN_ID)

    print("[3/5] Fetching S4 inputs and result...")
    s4_inputs = await validator.get_s4_inputs(USE_CASE_ID)
    s4_result = await validator.get_s4_result(USE_CASE_ID, S4_RUN_ID)

    # Run validations
    print("\n[4/5] Running S2→S3 data flow validation...")
    s2_to_s3_validation = validator.validate_s2_to_s3_flow(s2_result, s3_inputs)

    print("[5/5] Running S3→S4 data flow validation...")
    s3_to_s4_validation = validator.validate_s3_to_s4_flow(s3_result, s4_inputs)

    print("\n[BONUS] Running task extraction alignment check...")
    alignment_validation = validator.validate_task_extraction_alignment(s2_result, s3_result)

    print("\n[BONUS] Running hour constraints validation...")
    hours_validation = validator.validate_hour_constraints(s3_result, s4_result)

    # Print results
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)

    print("\n### S2→S3 Data Flow")
    print(f"  ✓ Complexity class match: {s2_to_s3_validation['complexity_class_match']}")
    print(f"  ✓ Effort weeks match: {s2_to_s3_validation['effort_weeks_match']}")
    print(f"  ✓ Process summary present: {s2_to_s3_validation['process_summary_present']}")
    print(f"  Overall: {'PASS' if s2_to_s3_validation['passed'] else 'FAIL'}")
    if s2_to_s3_validation['errors']:
        print(f"  Errors: {s2_to_s3_validation['errors']}")

    print("\n### S3→S4 Data Flow")
    print(f"  ✓ Build/SIT window match: {s3_to_s4_validation['build_sit_window_match']}")
    print(f"  ✓ Task extraction present: {s3_to_s4_validation['task_extraction_present']}")
    print(f"  Overall: {'PASS' if s3_to_s4_validation['passed'] else 'FAIL'}")
    if s3_to_s4_validation['errors']:
        print(f"  Errors: {s3_to_s4_validation['errors']}")

    print("\n### Task Extraction Alignment")
    print(f"  ✓ Activities aligned: {alignment_validation['activities_aligned']}")
    print(f"  ✓ Systems referenced: {alignment_validation['systems_referenced']}")
    print(f"  ✓ No new flows: {alignment_validation['no_new_flows']}")
    print(f"  Alignment score: {alignment_validation['alignment_score']:.1%}")
    print(f"  Overall: {'PASS' if alignment_validation['passed'] else 'FAIL'}")
    if alignment_validation['warnings']:
        print(f"  Warnings: {alignment_validation['warnings']}")

    print("\n### Hour Constraints")
    print(f"  ✓ S3 hours valid: {hours_validation['s3_hours_valid']}")
    print(f"  ✓ S4 hours valid: {hours_validation['s4_hours_valid']}")
    print(f"  ✓ S3-S4 hours match: {hours_validation['s3_s4_hours_match']}")
    print(f"  Overall: {'PASS' if hours_validation['passed'] else 'FAIL'}")
    if hours_validation['errors']:
        print(f"  Errors: {hours_validation['errors']}")

    # Overall assessment
    all_passed = (
        s2_to_s3_validation['passed'] and
        s3_to_s4_validation['passed'] and
        alignment_validation['passed'] and
        hours_validation['passed']
    )

    print("\n" + "="*80)
    print(f"OVERALL DATA FLOW VALIDATION: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("="*80)

    # Save detailed report
    report = {
        "s2_to_s3": s2_to_s3_validation,
        "s3_to_s4": s3_to_s4_validation,
        "alignment": alignment_validation,
        "hour_constraints": hours_validation,
        "overall_passed": all_passed
    }

    report_path = "/home/anirban/workspace/projects/rpa-intelligence/backend/tests/e2e/data_flow_validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDetailed report saved to: {report_path}")

    # Assert for pytest
    assert all_passed, "Data flow validation failed - see report for details"


if __name__ == "__main__":
    """
    Run validation directly with actual test IDs.
    Usage: uv run python tests/e2e/test_data_flow_validation.py
    """
    import asyncio
    import sys

    if len(sys.argv) >= 5:
        # Command line args: use_case_id s2_run_id s3_run_id s4_run_id
        USE_CASE_ID = sys.argv[1]
        S2_RUN_ID = sys.argv[2]
        S3_RUN_ID = sys.argv[3]
        S4_RUN_ID = sys.argv[4]

        # Patch the test function
        import unittest.mock as mock
        with mock.patch.dict(globals(), {
            'USE_CASE_ID': USE_CASE_ID,
            'S2_RUN_ID': S2_RUN_ID,
            'S3_RUN_ID': S3_RUN_ID,
            'S4_RUN_ID': S4_RUN_ID
        }):
            asyncio.run(test_full_data_flow_validation())
    else:
        print("Usage: python test_data_flow_validation.py <use_case_id> <s2_run_id> <s3_run_id> <s4_run_id>")
        print("\nOr run with pytest after updating IDs in the test function.")
        sys.exit(1)
