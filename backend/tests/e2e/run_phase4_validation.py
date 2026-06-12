#!/usr/bin/env python3
"""
Phase 4: Data Flow Validation - Standalone Runner
Uses existing test result JSON files to validate data contracts.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


class Phase4Validator:
    """Validates data flow contracts from saved test results"""

    def __init__(self, test_results: Dict[str, Any]):
        self.test_results = test_results
        self.validation_report = {
            "s2_to_s3_flow": {},
            "task_extraction_alignment": {},
            "hour_constraints": {},
            "overall_passed": False
        }

    def validate_s2_to_s3_flow(self) -> Dict[str, Any]:
        """Validate S2→S3 data flow contract"""
        print("\n" + "="*80)
        print("PHASE 4.1: S2→S3 DATA FLOW VALIDATION")
        print("="*80)

        results = {
            "complexity_class_match": False,
            "effort_weeks_match": False,
            "process_summary_present": False,
            "source_tags_correct": False,
            "errors": [],
            "warnings": []
        }

        # Extract S2 outputs
        s2_result = self.test_results.get("s2_run", {}).get("result", {})
        s2_complexity = s2_result.get("complexity_class")
        s2_effort_max = s2_result.get("effort_max_weeks")
        s2_effort_min = s2_result.get("effort_min_weeks")
        s2_process_summary = s2_result.get("process_summary", {})

        # Extract S3 inputs
        s3_inputs = self.test_results.get("s3_inputs_loaded", {})
        s3_complexity = s3_inputs.get("complexity_class")
        s3_effort_weeks = s3_inputs.get("effort_weeks")

        print(f"\n[CHECK 1] Complexity Class Transfer")
        print(f"  S2 complexity_class: {s2_complexity}")
        print(f"  S3 complexity_class: {s3_complexity}")

        if s2_complexity == s3_complexity:
            results["complexity_class_match"] = True
            print(f"  ✅ PASS - Complexity class matches")
        else:
            error = f"Complexity class mismatch: S2={s2_complexity}, S3={s3_complexity}"
            results["errors"].append(error)
            print(f"  ❌ FAIL - {error}")

        print(f"\n[CHECK 2] Effort Weeks Transfer")
        print(f"  S2 effort_min_weeks: {s2_effort_min}")
        print(f"  S2 effort_max_weeks: {s2_effort_max}")
        print(f"  S3 effort_weeks: {s3_effort_weeks}")

        if s3_effort_weeks == s2_effort_max or s3_effort_weeks == s2_effort_min:
            results["effort_weeks_match"] = True
            print(f"  ✅ PASS - Effort weeks matches S2 value")
        else:
            error = f"Effort weeks mismatch: S2_max={s2_effort_max}, S2_min={s2_effort_min}, S3={s3_effort_weeks}"
            results["errors"].append(error)
            print(f"  ❌ FAIL - {error}")

        print(f"\n[CHECK 3] Process Summary Transfer")
        required_fields = ["overall_summary", "key_activities", "key_logical_points", "key_applications"]

        if s2_process_summary:
            missing_fields = [f for f in required_fields if f not in s2_process_summary]
            if not missing_fields:
                results["process_summary_present"] = True
                print(f"  ✅ PASS - Process summary has all required fields")
                print(f"    - overall_summary: {len(s2_process_summary.get('overall_summary', ''))} chars")
                print(f"    - key_activities: {len(s2_process_summary.get('key_activities', []))} items")
                print(f"    - key_logical_points: {len(s2_process_summary.get('key_logical_points', []))} items")
                print(f"    - key_applications: {len(s2_process_summary.get('key_applications', []))} items")
            else:
                error = f"Process summary missing fields: {missing_fields}"
                results["errors"].append(error)
                print(f"  ❌ FAIL - {error}")
        else:
            error = "Process summary not present in S2 result"
            results["errors"].append(error)
            print(f"  ❌ FAIL - {error}")

        print(f"\n[CHECK 4] Source Tags")
        s3_complexity_source = s3_inputs.get("complexity_class_source")
        s3_effort_source = s3_inputs.get("effort_weeks_source")

        print(f"  S3 complexity_class_source: {s3_complexity_source}")
        print(f"  S3 effort_weeks_source: {s3_effort_source}")

        if s3_complexity_source == "from_s2" and s3_effort_source == "from_s2":
            results["source_tags_correct"] = True
            print(f"  ✅ PASS - Source tags correctly set to 'from_s2'")
        else:
            warning = f"Source tags not 'from_s2': complexity={s3_complexity_source}, effort={s3_effort_source}"
            results["warnings"].append(warning)
            print(f"  ⚠️  WARNING - {warning}")

        results["passed"] = (
            results["complexity_class_match"] and
            results["effort_weeks_match"] and
            results["process_summary_present"]
        )

        print(f"\n{'='*80}")
        print(f"S2→S3 FLOW: {'✅ PASS' if results['passed'] else '❌ FAIL'}")
        print(f"{'='*80}")

        return results

    def validate_task_extraction_alignment(self) -> Dict[str, Any]:
        """Validate S3 task extraction aligns with S2 process summary"""
        print("\n" + "="*80)
        print("PHASE 4.2: TASK EXTRACTION ALIGNMENT VALIDATION")
        print("="*80)

        results = {
            "activities_aligned": False,
            "systems_referenced": False,
            "no_new_flows": True,
            "alignment_score": 0.0,
            "errors": [],
            "warnings": []
        }

        # Extract S2 process summary
        s2_summary = self.test_results.get("s2_run", {}).get("result", {}).get("process_summary", {})
        s2_activities = s2_summary.get("key_activities", [])
        s2_applications = s2_summary.get("key_applications", [])

        # Extract S3 task extraction
        s3_extraction = self.test_results.get("task_extraction", {})
        s3_activities = s3_extraction.get("activities", [])

        print(f"\n[CHECK 1] Activity Alignment")
        print(f"  S2 key_activities count: {len(s2_activities)}")
        print(f"  S3 activities count: {len(s3_activities)}")

        if not s2_activities:
            results["errors"].append("S2 has no key_activities in process_summary")
            return results

        if not s3_activities:
            results["errors"].append("S3 has no activities in task_extraction")
            return results

        # Print S2 activities
        print(f"\n  S2 Activities:")
        for i, act in enumerate(s2_activities, 1):
            print(f"    {i}. {act}")

        # Extract S3 activity names
        s3_activity_names = [act.get("name", "") for act in s3_activities]

        # Print S3 activities
        print(f"\n  S3 Activities:")
        for i, act_name in enumerate(s3_activity_names, 1):
            print(f"    {i}. {act_name}")

        # Check alignment
        aligned_count = 0
        alignment_details = []

        for s2_activity in s2_activities:
            s2_lower = s2_activity.lower()
            s2_keywords = set(s2_lower.split())

            # Check if any S3 activity references this S2 activity
            matched = False
            for s3_name in s3_activity_names:
                s3_lower = s3_name.lower()
                s3_keywords = set(s3_lower.split())

                # Check for keyword overlap
                overlap = s2_keywords & s3_keywords
                # Remove common words
                meaningful_overlap = overlap - {"and", "the", "to", "from", "in", "for", "with", "a", "an"}

                if len(meaningful_overlap) >= 2:  # At least 2 meaningful words in common
                    aligned_count += 1
                    alignment_details.append(f"'{s2_activity}' → '{s3_name}'")
                    matched = True
                    break

            if not matched:
                alignment_details.append(f"'{s2_activity}' → NOT FOUND")

        # Calculate alignment score
        alignment_score = aligned_count / len(s2_activities) if s2_activities else 0.0
        results["alignment_score"] = alignment_score

        print(f"\n  Alignment Details:")
        for detail in alignment_details:
            symbol = "✓" if "→ NOT FOUND" not in detail else "✗"
            print(f"    {symbol} {detail}")

        print(f"\n  Alignment Score: {alignment_score:.1%} ({aligned_count}/{len(s2_activities)})")

        if alignment_score >= 0.7:  # 70% threshold
            results["activities_aligned"] = True
            print(f"  ✅ PASS - Alignment score meets threshold (≥70%)")
        else:
            warning = f"Low alignment score: {alignment_score:.1%}. Only {aligned_count}/{len(s2_activities)} S2 activities referenced in S3"
            results["warnings"].append(warning)
            print(f"  ⚠️  WARNING - {warning}")

        print(f"\n[CHECK 2] System/Application References")
        print(f"  S2 applications: {s2_applications}")

        if s2_applications:
            referenced_systems = 0
            for app in s2_applications:
                app_lower = app.lower()
                # Check if any S3 activity mentions this application
                for s3_name in s3_activity_names:
                    if app_lower in s3_name.lower():
                        referenced_systems += 1
                        print(f"    ✓ '{app}' referenced in S3 activities")
                        break

            if referenced_systems > 0:
                results["systems_referenced"] = True
                print(f"  ✅ PASS - {referenced_systems}/{len(s2_applications)} systems referenced")
            else:
                warning = f"None of S2 applications {s2_applications} referenced in S3 activities"
                results["warnings"].append(warning)
                print(f"  ⚠️  WARNING - {warning}")
        else:
            print(f"  ⏭️  SKIP - No S2 applications to check")

        print(f"\n[CHECK 3] No Entirely New Process Flows")
        # Check for suspicious new activities
        allowed_keywords = ["login", "logout", "setup", "initialize", "error", "validation",
                           "exception", "handling", "logging", "authentication"]
        suspicious_activities = []

        # Extract S2 business rules to check for derivations
        s2_business_rules = s2_summary.get("key_logical_points", [])

        for s3_name in s3_activity_names:
            s3_lower = s3_name.lower()
            is_allowed = any(kw in s3_lower for kw in allowed_keywords)

            # Check if it references S2 activities
            s3_keywords = set(s3_lower.split())
            s2_all_keywords = set()
            for s2_activity in s2_activities:
                s2_all_keywords.update(s2_activity.lower().split())

            has_s2_activity_reference = len(s3_keywords & s2_all_keywords) >= 2

            # NEW: Check if it references S2 business rules
            has_s2_rule_reference = False
            for rule in s2_business_rules:
                rule_lower = rule.lower()
                # Check for keyword presence with simple stemming
                # e.g., "split" matches "splitting", "order" matches "orders"
                keywords_to_check = [
                    kw for kw in s3_keywords
                    if len(kw) > 3 and kw not in {"and", "the", "to", "from", "in", "for", "with", "a", "an", "of", "is", "be", "must"}
                ]

                matches = 0
                for kw in keywords_to_check:
                    # Simple stemming: check if keyword or its stem appears in rule
                    if kw in rule_lower or kw[:-1] in rule_lower or kw[:-3] in rule_lower:
                        matches += 1
                    # Also check if plural/singular forms match
                    if kw.endswith('s') and kw[:-1] in rule_lower:
                        matches += 1
                    elif kw + 's' in rule_lower:
                        matches += 1

                if matches >= 2:
                    has_s2_rule_reference = True
                    break

            if not is_allowed and not has_s2_activity_reference and not has_s2_rule_reference:
                suspicious_activities.append(s3_name)

        if suspicious_activities:
            results["no_new_flows"] = False
            warning = f"Suspicious new activities not in S2: {suspicious_activities}"
            results["warnings"].append(warning)
            print(f"  ⚠️  WARNING - {warning}")
        else:
            results["no_new_flows"] = True
            print(f"  ✅ PASS - No suspicious new activities detected")

        results["passed"] = (
            results["activities_aligned"] and
            results["no_new_flows"]
        )

        print(f"\n{'='*80}")
        print(f"ALIGNMENT: {'✅ PASS' if results['passed'] else '❌ FAIL'}")
        print(f"{'='*80}")

        return results

    def validate_hour_constraints(self) -> Dict[str, Any]:
        """Validate hour constraints in S3 task extraction"""
        print("\n" + "="*80)
        print("PHASE 4.3: HOUR CONSTRAINTS VALIDATION")
        print("="*80)

        results = {
            "s3_hours_valid": False,
            "total_hours_match_effort": False,
            "errors": [],
            "warnings": []
        }

        # Extract S3 task extraction
        s3_extraction = self.test_results.get("task_extraction", {})
        s3_total_effort = s3_extraction.get("total_net_hours", 0)
        s3_activities = s3_extraction.get("activities", [])

        # Extract S3 inputs for effort calculation
        s3_inputs = self.test_results.get("s3_inputs_loaded", {})
        effort_weeks = s3_inputs.get("effort_weeks", 0)
        expected_hours = effort_weeks * 40

        print(f"\n[CHECK 1] S3 Task Extraction Hour Sum")
        print(f"  Effort weeks: {effort_weeks}")
        print(f"  Expected total hours: {expected_hours} (weeks × 40)")
        print(f"  Declared total_net_hours: {s3_total_effort}")

        # Calculate actual hours from steps (applying reusability multipliers)
        calculated_hours = 0.0
        step_details = []

        for activity in s3_activities:
            if not isinstance(activity, dict):
                continue

            activity_name = activity.get("name", "Unknown")
            steps = activity.get("steps", [])
            activity_hours = 0.0

            for step in steps:
                if not isinstance(step, dict):
                    continue

                hours = step.get("weight_hours", 0)
                reusability = step.get("reusability", "")

                # Apply reusability multipliers (matching agent logic)
                if reusability == "full":
                    net_hours = 0.0  # Existing component, don't count
                elif reusability == "partial":
                    net_hours = hours * 0.5  # Adapted component, count 50%
                else:  # "none"
                    net_hours = hours  # Custom work, count 100%

                calculated_hours += net_hours
                activity_hours += net_hours

            step_details.append(f"    {activity_name}: {activity_hours:.1f} hours")

        print(f"\n  Activity Hour Breakdown:")
        for detail in step_details:
            print(detail)

        print(f"\n  Calculated hours (with reusability multipliers): {calculated_hours:.1f}")

        # Validate hour constraint
        if abs(calculated_hours - s3_total_effort) < 0.1:
            results["s3_hours_valid"] = True
            print(f"  ✅ PASS - Calculated hours match declared total")
        else:
            error = f"S3 hour constraint violated: declared {s3_total_effort}, calculated {calculated_hours}"
            results["errors"].append(error)
            print(f"  ❌ FAIL - {error}")

        # Validate total hours match effort weeks (with 30% tolerance)
        print(f"\n[CHECK 2] Total Hours Match Effort Weeks (±30% tolerance)")
        tolerance = 0.3  # 30% tolerance (matching agent settings)
        ratio = abs(1 - (s3_total_effort / expected_hours)) if expected_hours > 0 else 1.0

        if ratio < tolerance:
            results["total_hours_match_effort"] = True
            print(f"  ✅ PASS - Total hours within tolerance")
            print(f"    Expected: {expected_hours}h ({effort_weeks} weeks × 40)")
            print(f"    Actual: {s3_total_effort}h")
            print(f"    Ratio: {ratio:.1%} (threshold: {tolerance:.0%})")
        else:
            error = f"Total hours outside {tolerance*100}% tolerance: ratio={ratio:.1%}, expected {expected_hours}h, got {s3_total_effort}h"
            results["errors"].append(error)
            print(f"  ❌ FAIL - {error}")

        results["passed"] = (
            results["s3_hours_valid"] and
            results["total_hours_match_effort"]
        )

        print(f"\n{'='*80}")
        print(f"HOUR CONSTRAINTS: {'✅ PASS' if results['passed'] else '❌ FAIL'}")
        print(f"{'='*80}")

        return results

    def run_full_validation(self) -> Dict[str, Any]:
        """Run all Phase 4 validations"""
        print("\n" + "="*80)
        print("PHASE 4: DATA FLOW VALIDATION - START")
        print("="*80)

        # Run all validations
        self.validation_report["s2_to_s3_flow"] = self.validate_s2_to_s3_flow()
        self.validation_report["task_extraction_alignment"] = self.validate_task_extraction_alignment()
        self.validation_report["hour_constraints"] = self.validate_hour_constraints()

        # Overall assessment
        all_passed = (
            self.validation_report["s2_to_s3_flow"]["passed"] and
            self.validation_report["task_extraction_alignment"]["passed"] and
            self.validation_report["hour_constraints"]["passed"]
        )

        self.validation_report["overall_passed"] = all_passed

        # Print summary
        print("\n" + "="*80)
        print("PHASE 4 VALIDATION SUMMARY")
        print("="*80)

        checks = [
            ("S2→S3 Data Flow", self.validation_report["s2_to_s3_flow"]["passed"]),
            ("Task Extraction Alignment", self.validation_report["task_extraction_alignment"]["passed"]),
            ("Hour Constraints", self.validation_report["hour_constraints"]["passed"])
        ]

        for check_name, passed in checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {check_name}: {status}")

        print(f"\n{'='*80}")
        print(f"OVERALL PHASE 4: {'✅ PASS' if all_passed else '❌ FAIL'}")
        print(f"{'='*80}")

        return self.validation_report


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python run_phase4_validation.py <path_to_test_results.json>")
        print("\nExample:")
        print("  python run_phase4_validation.py s2_to_s3_test_results_20260612_041519.json")
        sys.exit(1)

    # Load test results
    test_results_file = Path(sys.argv[1])
    if not test_results_file.exists():
        print(f"Error: File not found: {test_results_file}")
        sys.exit(1)

    print(f"Loading test results from: {test_results_file}")
    with open(test_results_file, "r") as f:
        test_results = json.load(f)

    # Run validation
    validator = Phase4Validator(test_results)
    report = validator.run_full_validation()

    # Save report
    report_file = test_results_file.parent / "phase4_validation_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDetailed report saved to: {report_file}")

    # Exit with appropriate code
    sys.exit(0 if report["overall_passed"] else 1)


if __name__ == "__main__":
    main()
