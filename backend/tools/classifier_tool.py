"""
Classifier tool — maps total score to complexity class.
Thin wrapper around core/scoring/classifier.
Pure Python, no LLM calls.
"""
from pydantic import BaseModel
from core.models.scoring import ComplexityClass, AttributeBands
from core.scoring.classifier import classify


class ClassificationResult(BaseModel):
    """Result of complexity classification."""
    complexity_class: ComplexityClass


def classify_complexity(total_score: int, bands: AttributeBands) -> ClassificationResult:
    """
    Classify total score into complexity class.
    Detects XS special case: max 2 attributes, all XS.

    Args:
        total_score: Sum of all attribute weights
        bands: Original AttributeBands to check XS special case

    Returns:
        ClassificationResult with complexity_class
    """
    # XS special case: max 2 attributes selected, all in XS column
    all_bands = [bands.activities, bands.business_rules, bands.layouts, bands.interfaces, bands.technology]
    xs_count = sum(1 for b in all_bands if b == "XS")
    non_xs_count = len(all_bands) - xs_count

    # If at most 2 non-XS attributes and all others are XS
    is_xs_special = non_xs_count <= 2 and xs_count >= 3

    complexity_class = classify(total_score, is_xs_special_case=is_xs_special)

    return ClassificationResult(complexity_class=complexity_class)
