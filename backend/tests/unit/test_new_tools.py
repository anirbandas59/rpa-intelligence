"""
Tests for new Phase 3 tools: task extraction parser, tracker sequencer, export formulas.
"""

from datetime import date, timedelta

from tools.analysis.task_extraction_tool import (
    TaskExtractionResult,
    parse_task_extraction,
    validate_hour_sum,
)
from tools.output.export_tool import FORMULA_SP, formula_dev_status
from tools.output.tracker_sequencer import (
    SequencerInput,
    TrackerRow,
    sequence_dates,
)


class TestTaskExtractionTool:
    """Test task extraction parser and validator."""

    def test_parse_valid_json(self):
        """Test parsing valid task extraction JSON."""
        raw_json = """
        {
          "activities": [
            {
              "name": "User Authentication",
              "steps": [
                {
                  "description": "Build login form",
                  "weight_hours": 8.0,
                  "reusability": "none"
                },
                {
                  "description": "Integrate with OAuth",
                  "weight_hours": 12.0,
                  "reusability": "partial"
                }
              ]
            }
          ],
          "total_net_hours": 20.0,
          "verification_passed": true
        }
        """

        result = parse_task_extraction(raw_json)

        assert isinstance(result, TaskExtractionResult)
        assert len(result.activities) == 1
        assert result.activities[0].name == "User Authentication"
        assert len(result.activities[0].steps) == 2
        assert result.total_net_hours == 20.0
        assert result.verification_passed is True

    def test_parse_with_markdown_fences(self):
        """Test parsing JSON wrapped in markdown fences."""
        raw_json = """```json
        {
          "activities": [],
          "total_net_hours": 0.0,
          "verification_passed": true
        }
        ```"""

        result = parse_task_extraction(raw_json)

        assert isinstance(result, TaskExtractionResult)
        assert len(result.activities) == 0

    def test_validate_hour_sum_passes(self):
        """Test hour sum validation passes when sum matches."""
        result = TaskExtractionResult(
            activities=[
                {
                    "name": "Activity 1",
                    "steps": [
                        {"description": "Step 1", "weight_hours": 10.0, "reusability": "none"},
                        {"description": "Step 2", "weight_hours": 5.0, "reusability": "partial"},
                        {
                            "description": "Step 3",
                            "weight_hours": 3.0,
                            "reusability": "full",
                        },  # Excluded
                    ],
                }
            ],
            total_net_hours=15.0,
            verification_passed=True,
        )

        budget = 15.0
        is_valid = validate_hour_sum(result, budget, tolerance=0.5)

        assert is_valid is True

    def test_validate_hour_sum_fails(self):
        """Test hour sum validation fails when sum mismatches."""
        result = TaskExtractionResult(
            activities=[
                {
                    "name": "Activity 1",
                    "steps": [
                        {"description": "Step 1", "weight_hours": 10.0, "reusability": "none"},
                    ],
                }
            ],
            total_net_hours=10.0,
            verification_passed=True,
        )

        budget = 20.0
        is_valid = validate_hour_sum(result, budget, tolerance=0.5)

        assert is_valid is False


class TestTrackerSequencer:
    """Test date sequencer for tracker rows."""

    def test_sequence_dates_basic(self):
        """Test basic date sequencing."""
        tracker_rows = [
            TrackerRow(feature="feature-1", hours=10.0, priority="MUST"),
            TrackerRow(feature="feature-2", hours=20.0, priority="MUST"),
            TrackerRow(feature="feature-3", hours=10.0, priority="SHOULD"),
        ]

        input_data = SequencerInput(
            tracker_rows=tracker_rows,
            build_sit_start=date(2025, 1, 1),
            build_sit_end=date(2025, 1, 31),  # 30 days
            total_effort_hours=40.0,
        )

        sequenced = sequence_dates(input_data)

        assert len(sequenced) == 3
        # First row starts on start_date
        assert sequenced[0].start_date == date(2025, 1, 1)
        # Last row ends on end_date
        assert sequenced[-1].end_date == date(2025, 1, 31)
        # Dates are sequential (no gaps)
        assert sequenced[1].start_date == sequenced[0].end_date + timedelta(days=1)

    def test_sequence_dates_proportional(self):
        """Test that rows get proportional allocation."""

        tracker_rows = [
            TrackerRow(feature="feature-1", hours=20.0, priority="MUST"),  # 50% of hours
            TrackerRow(feature="feature-2", hours=20.0, priority="MUST"),  # 50% of hours
        ]

        input_data = SequencerInput(
            tracker_rows=tracker_rows,
            build_sit_start=date(2025, 1, 1),
            build_sit_end=date(2025, 1, 10),  # 9 days
            total_effort_hours=40.0,
        )

        sequenced = sequence_dates(input_data)

        # Each row should get ~50% of calendar days (roughly 4-5 days each)
        row1_days = (sequenced[0].end_date - sequenced[0].start_date).days + 1
        row2_days = (sequenced[1].end_date - sequenced[1].start_date).days + 1

        # Both should be close to 50% of 9 days
        assert row1_days >= 3
        assert row2_days >= 3
        # Last row ends exactly on end_date
        assert sequenced[-1].end_date == date(2025, 1, 10)


class TestExportTool:
    """Test formula generation for export."""

    def test_formula_sp_constant(self):
        """Test SP formula is correct."""
        assert FORMULA_SP == "=ROUND($C$16*Table5[[#This Row],[Hours]],2)"

    def test_formula_dev_status_generation(self):
        """Test dev status formula generation."""
        formula = formula_dev_status(19)

        assert "K19" in formula  # References completion % column
        assert "D19" in formula  # References acceptance status column
        assert "VLOOKUP" in formula
        assert "COMPL_STATUS" in formula

    def test_formula_dev_status_row_specific(self):
        """Test dev status formula is row-specific."""
        formula_row_20 = formula_dev_status(20)
        formula_row_21 = formula_dev_status(21)

        assert "K20" in formula_row_20
        assert "D20" in formula_row_20
        assert "K21" in formula_row_21
        assert "D21" in formula_row_21
        assert formula_row_20 != formula_row_21
