"""
Tool to calculate weighted complexity scores from attribute scores.

This module takes a list of AttributeScore objects and produces:
1. Total weighted score (sum of all attribute weights)
2. Complexity tier classification using the Phase 1 classifier
3. Confidence score based on distance from tier boundaries
4. List of attributes that exceed XL ceilings

Pure Python — no LLM calls.
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
