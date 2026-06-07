"""
Effort estimation — maps complexity classes to time estimates (weeks and sprints).

Loads effort data from data/reference/effort_table.json which stores values in
business days, then converts to weeks using a 5-day work week. Provides both
time-based estimates (weeks) and sprint-based estimates for project planning.

Key functions:
- load_effort_table(): Loads and caches effort data from JSON
- get_effort(): Maps complexity class to effort estimates (weeks + sprints)
- _to_weeks(): Utility for day-to-week conversion

Source data format: {"efforts": {"XS": {"total": days, "sprints": count}, ...}}
Pure Python implementation with no LLM calls.
"""

import json
from pathlib import Path

from core.exceptions import ScoringValidationError

_TABLE_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "effort_table.json"
_TABLE_CACHE: dict | None = None

_DAYS_PER_WEEK = 5  # Business week (Mon-Fri)


def _to_weeks(days) -> int:
    """
    Convert days to weeks using 5-day business week.

    Handles both single values and ranges. For ranges, uses the maximum
    value to provide conservative estimates.

    Args:
        days: Either an integer (single value) or list [min, max] (range)

    Returns:
        Number of weeks, rounded to nearest integer
    """
    if isinstance(days, list):
        # Range: use max value for conservative estimate
        return round(days[1] / _DAYS_PER_WEEK)
    # Single value: direct conversion
    return round(days / _DAYS_PER_WEEK)


def load_effort_table() -> dict:
    """
    Load and cache effort table from JSON file.

    Reads data/reference/effort_table.json on first call and caches
    the result for subsequent calls. The JSON contains effort estimates
    in business days that are converted to weeks by get_effort().

    Returns:
        Parsed effort data dictionary with structure:
        {"efforts": {"XS": {"total": days, "sprints": count}, ...}}
    """
    global _TABLE_CACHE
    if _TABLE_CACHE is None:
        with open(_TABLE_PATH) as f:
            _TABLE_CACHE = json.load(f)
    return _TABLE_CACHE


def get_effort(complexity_class: str) -> dict:
    """
    Get effort estimates for a complexity class.

    Retrieves time and sprint estimates from the effort table and converts
    day-based values to weeks using a 5-day business week. Handles both
    single values and ranges for flexibility in estimation.

    Args:
        complexity_class: Complexity tier ("XS" | "S" | "M" | "L" | "XL")

    Returns:
        Dictionary with effort estimates:
        {
            "min_weeks": int,      # Minimum time estimate in weeks
            "max_weeks": int,      # Maximum time estimate in weeks
            "sprint_min": int,     # Minimum sprint count
            "sprint_max": int      # Maximum sprint count
        }

    Raises:
        ScoringValidationError: If complexity_class is not in effort table
    """
    data = load_effort_table()

    if complexity_class not in data["efforts"]:
        raise ScoringValidationError(f"Unknown complexity class: {complexity_class}")

    row = data["efforts"][complexity_class]
    total = row["total"]
    sprints = row["sprints"]

    # Convert total days to weeks
    if isinstance(total, list):
        # Range: [min_days, max_days] → convert each bound
        min_weeks = round(total[0] / _DAYS_PER_WEEK)
        max_weeks = round(total[1] / _DAYS_PER_WEEK)
    else:
        # Single value: use same for min and max
        min_weeks = max_weeks = round(total / _DAYS_PER_WEEK)

    # Extract sprint counts (already in sprint units, no conversion needed)
    if isinstance(sprints, list):
        sprint_min, sprint_max = sprints[0], sprints[1]
    else:
        sprint_min = sprint_max = sprints

    return {
        "min_weeks": min_weeks,
        "max_weeks": max_weeks,
        "sprint_min": sprint_min,
        "sprint_max": sprint_max,
    }
