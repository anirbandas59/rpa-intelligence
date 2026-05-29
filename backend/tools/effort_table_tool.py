"""
Effort table tool — maps complexity class to effort estimates.
Thin wrapper around core/scoring/effort_table.
Pure Python, no LLM calls.
"""

from pydantic import BaseModel
from core.models.scoring import ComplexityClass
from core.scoring.effort_table import get_effort


class EffortResult(BaseModel):
    """Result of effort lookup."""

    min_weeks: int
    max_weeks: int
    sprint_min: int
    sprint_max: int


def lookup_effort(complexity_class: ComplexityClass) -> EffortResult:
    """
    Look up effort estimates for a complexity class.

    Args:
        complexity_class: XS | S | M | L | XL

    Returns:
        EffortResult with min/max weeks and sprints
    """
    effort_data = get_effort(complexity_class)

    return EffortResult(
        min_weeks=effort_data["min_weeks"],
        max_weeks=effort_data["max_weeks"],
        sprint_min=effort_data["sprint_min"],
        sprint_max=effort_data["sprint_max"],
    )
