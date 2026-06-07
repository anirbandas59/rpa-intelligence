"""
Complexity classifier — maps cumulative weight scores to complexity classes.

Implements the RPA complexity classification algorithm using a score-to-band
mapping system. Supports five complexity tiers (XS/S/M/L/XL) with special
handling for XS cases. Also provides confidence scoring based on position
within tier boundaries to identify edge cases requiring review.

Key functions:
- classify(): Maps total score to complexity class
- get_confidence_score(): Calculates confidence based on distance from boundaries

Pure Python implementation with no LLM calls.
"""

from core.constants import ComplexityTier
from core.exceptions import ScoringValidationError
from core.models.scoring import ComplexityClass

# XS is a special case handled before numeric classification
_BANDS: list[tuple[ComplexityClass, int, int]] = [
    ("S", 7, 8),
    ("M", 9, 15),
    ("L", 16, 22),
    ("XL", 23, 28),
]


def classify(total_score: int, is_xs_special_case: bool = False) -> ComplexityClass:
    """
    Map cumulative weight score to complexity class using defined band ranges.

    Processes scores from 7-28 into five complexity classes. XS is a special
    case requiring caller detection (max 2 attributes, all in XS column).
    Numeric bands: S(7-8), M(9-15), L(16-22), XL(23-28).

    Args:
        total_score: Cumulative weight score from attribute scoring (7-28 range)
        is_xs_special_case: True if XS special case detected by caller (default False)

    Returns:
        Complexity class string: "XS" | "S" | "M" | "L" | "XL"

    Raises:
        ScoringValidationError: If score falls outside valid range (7-28) and not XS special case
    """
    if is_xs_special_case:
        return "XS"
    for cls, lo, hi in _BANDS:
        if lo <= total_score <= hi:
            return cls
    raise ScoringValidationError(
        f"Score {total_score} does not map to any complexity class. Valid range: 7–28 (or XS)."
    )


def get_confidence_score(total_score: int, tier: ComplexityTier) -> float:
    """
    Calculate confidence score based on distance from tier boundaries.

    Confidence is higher when the score is in the middle of a tier
    range and lower when near boundaries. This helps identify edge
    cases where the classification may be uncertain and additional
    review or follow-up questions may be beneficial.

    Args:
        total_score: The score within the tier
        tier: The ComplexityTier for this score

    Returns:
        Confidence score between 0.05 and 1.0, rounded to 2 decimals.
        Scores <0.5 may trigger follow-up questions in Stage 1.
    """
    tier_min = tier.min_score()
    tier_max = tier.max_score()
    tier_range = tier_max - tier_min

    if tier_range == 0:
        # Special case: single-value tier range
        return 0.5

    # Distance from nearest edge
    distance_from_min = total_score - tier_min
    distance_from_max = tier_max - total_score
    distance_from_edge = min(distance_from_min, distance_from_max)

    # Confidence: how far from edge relative to half the range
    confidence = distance_from_edge / (tier_range / 2)

    # Clamp to 0.05-1.0
    confidence = max(0.05, min(1.0, confidence))

    # Round to 2 decimal places
    return round(confidence, 2)
