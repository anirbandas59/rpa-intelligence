import json
from pathlib import Path
from core.exceptions import ScoringValidationError

_TABLE_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "effort_table.json"

_DAYS_PER_WEEK = 5


def _to_weeks(days) -> int:
    """Convert days (int or [min,max] list) to whole weeks, rounded up."""
    if isinstance(days, list):
        return round(days[1] / _DAYS_PER_WEEK)  # use max of range
    return round(days / _DAYS_PER_WEEK)


def get_effort(complexity_class: str) -> dict:
    """
    Returns {min_weeks, max_weeks, sprint_min, sprint_max} for a complexity class.
    Converts the source file's day-based values to weeks.
    """
    with open(_TABLE_PATH) as f:
        data = json.load(f)

    if complexity_class not in data["efforts"]:
        raise ScoringValidationError(f"Unknown complexity class: {complexity_class}")

    row = data["efforts"][complexity_class]
    total = row["total"]
    sprints = row["sprints"]

    if isinstance(total, list):
        min_weeks = round(total[0] / _DAYS_PER_WEEK)
        max_weeks = round(total[1] / _DAYS_PER_WEEK)
    else:
        min_weeks = max_weeks = round(total / _DAYS_PER_WEEK)

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
