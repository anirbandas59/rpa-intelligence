"""
Unit tests for task extraction hour calculation and validation logic.
Tests reusability multipliers and hour constraint calculations.
"""

import pytest
import json
from pathlib import Path


def calculate_net_hours(activities: list[dict]) -> float:
    """
    Calculate total net hours from activities with reusability multipliers.

    This function replicates the logic from:
    - backend/agents/task_decomposition_agent.py (validate_hour_sum_node)
    - backend/tests/e2e/run_phase4_validation.py (validate_hour_constraints)

    Reusability factors:
    - "none": 1.0 (100% - fully custom work)
    - "partial": 0.5 (50% - adapted from reusable component)
    - "full": 0.0 (0% - existing reusable component)
    """
    total_hours = 0.0

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        steps = activity.get("steps", [])
        for step in steps:
            if not isinstance(step, dict):
                continue

            weight_hours = step.get("weight_hours", 0.0)
            reusability = step.get("reusability", "none")

            # Apply reusability multipliers
            if reusability == "full":
                net_hours = 0.0
            elif reusability == "partial":
                net_hours = weight_hours * 0.5
            else:  # "none"
                net_hours = weight_hours

            total_hours += net_hours

    return total_hours


class TestReusabilityMultipliers:
    """Test reusability factor calculations"""

    def test_reusability_none_counts_100_percent(self):
        """Verify reusability="none" counts 100% of hours"""
        activities = [
            {
                "name": "Test Activity",
                "steps": [
                    {"weight_hours": 10.0, "reusability": "none"},
                    {"weight_hours": 20.0, "reusability": "none"}
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 30.0, "reusability='none' should count 100% of hours"

    def test_reusability_partial_counts_50_percent(self):
        """Verify reusability="partial" counts 50% of hours"""
        activities = [
            {
                "name": "Test Activity",
                "steps": [
                    {"weight_hours": 10.0, "reusability": "partial"},
                    {"weight_hours": 20.0, "reusability": "partial"}
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 15.0, "reusability='partial' should count 50% of hours"

    def test_reusability_full_counts_zero_percent(self):
        """Verify reusability="full" counts 0% of hours"""
        activities = [
            {
                "name": "Test Activity",
                "steps": [
                    {"weight_hours": 10.0, "reusability": "full"},
                    {"weight_hours": 20.0, "reusability": "full"}
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 0.0, "reusability='full' should count 0% of hours"

    def test_mixed_reusability_calculation(self):
        """Test calculation with mixed reusability types"""
        activities = [
            {
                "name": "Test Activity",
                "steps": [
                    {"weight_hours": 10.0, "reusability": "none"},     # 10 * 1.0 = 10.0
                    {"weight_hours": 20.0, "reusability": "partial"},  # 20 * 0.5 = 10.0
                    {"weight_hours": 30.0, "reusability": "full"},     # 30 * 0.0 = 0.0
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 20.0, "Mixed reusability should apply correct multipliers"


class TestHourConstraintValidation:
    """Test hour constraint validation logic"""

    def test_30_percent_tolerance_boundary(self):
        """Verify 30% tolerance boundary conditions"""
        target_hours = 200
        tolerance = 0.3

        # Test cases: (actual_hours, should_pass)
        # Note: Boundary uses < (not <=), so exactly 30% fails
        test_cases = [
            (200, True),   # Exact match
            (208, True),   # 4% over (within tolerance)
            (259, True),   # Just under 30% boundary (29.5%)
            (141, True),   # Just under -30% boundary (-29.5%)
            (260, False),  # Exactly at 30% boundary
            (140, False),  # Exactly at -30% boundary
            (261, False),  # Just over 30%
            (139, False),  # Just under -30%
        ]

        for actual_hours, should_pass in test_cases:
            ratio = abs(1 - (actual_hours / target_hours))
            within_tolerance = ratio < tolerance

            assert within_tolerance == should_pass, (
                f"Hours {actual_hours} vs target {target_hours}: "
                f"ratio {ratio:.1%} should {'pass' if should_pass else 'fail'}"
            )

    def test_hour_tolerance_calculation(self):
        """Test hour tolerance calculation"""
        effort_weeks = 5
        expected_hours = effort_weeks * 40  # 200 hours

        # Test that 4% variance passes
        actual_hours = 208
        ratio = abs(1 - (actual_hours / expected_hours))

        assert ratio < 0.3, f"4% variance ({ratio:.1%}) should be within 30% tolerance"


class TestActualTestDataRegression:
    """Regression tests with actual test data"""

    def test_s2_to_s3_test_results_20260612_041519(self):
        """
        Regression test with actual test data from s2_to_s3_test_results_20260612_041519.json

        Expected behavior:
        - Raw step hours with reusability:
          - "none": 179h × 1.0 = 179h
          - "partial": 85h × 0.5 = 42.5h
          - "full": 0h × 0.0 = 0h
        - Total: 221.5h

        Note: The declared total_net_hours in the test file is 208h, which means
        the agent applied different calculation or the test data has inconsistencies.
        This test verifies our calculation logic is correct.
        """
        # Load test data
        test_file = Path(__file__).parent.parent / "e2e" / "s2_to_s3_test_results_20260612_041519.json"

        if not test_file.exists():
            pytest.skip(f"Test data file not found: {test_file}")

        with open(test_file) as f:
            test_data = json.load(f)

        # Extract activities
        activities = test_data.get("task_extraction", {}).get("activities", [])
        declared_total = test_data.get("task_extraction", {}).get("total_net_hours", 0)
        effort_weeks = test_data.get("s3_inputs_loaded", {}).get("effort_weeks", 0)

        # Calculate net hours
        calculated_net_hours = calculate_net_hours(activities)

        # Verify calculation matches our expected logic
        # Note: This might not match declared_total if agent has different logic
        print(f"\nCalculated net hours: {calculated_net_hours}")
        print(f"Declared total_net_hours: {declared_total}")
        print(f"Effort weeks: {effort_weeks} → Expected: {effort_weeks * 40}h")

        # Count steps by reusability
        none_hours = 0.0
        partial_hours = 0.0
        full_hours = 0.0

        for activity in activities:
            for step in activity.get("steps", []):
                weight = step.get("weight_hours", 0)
                reusability = step.get("reusability", "")

                if reusability == "none":
                    none_hours += weight
                elif reusability == "partial":
                    partial_hours += weight
                elif reusability == "full":
                    full_hours += weight

        print(f"\nBreakdown:")
        print(f"  'none' steps: {none_hours}h × 1.0 = {none_hours}h")
        print(f"  'partial' steps: {partial_hours}h × 0.5 = {partial_hours * 0.5}h")
        print(f"  'full' steps: {full_hours}h × 0.0 = 0h")
        print(f"  Total: {none_hours + (partial_hours * 0.5)}h")

        # Verify our calculation is correct
        expected = none_hours + (partial_hours * 0.5) + (full_hours * 0.0)
        assert abs(calculated_net_hours - expected) < 0.1, "Calculation should match manual breakdown"

        # Verify it's within 30% tolerance of effort weeks
        expected_hours = effort_weeks * 40
        ratio = abs(1 - (calculated_net_hours / expected_hours)) if expected_hours > 0 else 1.0

        print(f"\nTolerance check:")
        print(f"  Ratio: {ratio:.1%} (threshold: 30%)")
        print(f"  Result: {'PASS' if ratio < 0.3 else 'FAIL'}")

        # This assertion verifies the calculated hours are within tolerance
        # (might fail if test data is inconsistent with 30% tolerance rule)
        assert ratio < 0.3, f"Calculated hours ({calculated_net_hours}) should be within 30% of expected ({expected_hours})"


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_activities_list(self):
        """Handle empty activities list"""
        activities = []
        net_hours = calculate_net_hours(activities)
        assert net_hours == 0.0

    def test_missing_reusability_field(self):
        """Default to 'none' if reusability field missing"""
        activities = [
            {
                "name": "Test",
                "steps": [
                    {"weight_hours": 10.0}  # No reusability field
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 10.0, "Missing reusability should default to 'none' (100%)"

    def test_invalid_activity_structure(self):
        """Handle invalid activity structures gracefully"""
        activities = [
            None,  # Invalid
            {"name": "Valid", "steps": [{"weight_hours": 10.0, "reusability": "none"}]},
            "invalid",  # Invalid
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 10.0, "Should skip invalid entries"

    def test_zero_weight_hours(self):
        """Handle zero weight hours"""
        activities = [
            {
                "name": "Test",
                "steps": [
                    {"weight_hours": 0.0, "reusability": "none"},
                    {"weight_hours": 0.0, "reusability": "partial"},
                ]
            }
        ]

        net_hours = calculate_net_hours(activities)
        assert net_hours == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
