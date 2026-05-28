"""
Weighted calculator tool — sums attribute weights.
Pure Python, no LLM calls.
"""
from pydantic import BaseModel


class TotalScoreResult(BaseModel):
    """Result of total score calculation."""
    total_score: int


def calculate_total(attribute_weights: dict[str, int]) -> TotalScoreResult:
    """
    Sum all attribute weights to produce total score.

    Args:
        attribute_weights: Dict mapping attribute names to weight integers

    Returns:
        TotalScoreResult with total_score
    """
    total = sum(attribute_weights.values())
    return TotalScoreResult(total_score=total)
