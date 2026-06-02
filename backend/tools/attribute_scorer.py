"""
Attribute scorer tool — maps AttributeBands to weight integers.
Pure Python, no LLM calls.
"""

from pydantic import BaseModel

from core.models.scoring import AttributeBands
from core.scoring.weight_matrix import get_weight, load_weight_matrix


class AttributeScoreResult(BaseModel):
    """Result of attribute scoring with individual weights."""

    activities_weight: int
    business_rules_weight: int
    layouts_weight: int
    interfaces_weight: int
    technology_weight: int
    attribute_weights: dict[str, int]


def score_attributes(bands: AttributeBands) -> AttributeScoreResult:
    """
    Given AttributeBands, return individual weights per attribute.
    Loads weight matrix from reference file.

    Args:
        bands: AttributeBands with XS/S/M/L/XL values

    Returns:
        AttributeScoreResult with individual weights and dict
    """
    matrix = load_weight_matrix()

    activities_weight = get_weight(matrix, "activities", bands.activities)
    business_rules_weight = get_weight(matrix, "business_rules", bands.business_rules)
    layouts_weight = get_weight(matrix, "layouts", bands.layouts)
    interfaces_weight = get_weight(matrix, "interfaces", bands.interfaces)
    technology_weight = get_weight(matrix, "technology", bands.technology)

    return AttributeScoreResult(
        activities_weight=activities_weight,
        business_rules_weight=business_rules_weight,
        layouts_weight=layouts_weight,
        interfaces_weight=interfaces_weight,
        technology_weight=technology_weight,
        attribute_weights={
            "activities": activities_weight,
            "business_rules": business_rules_weight,
            "layouts": layouts_weight,
            "interfaces": interfaces_weight,
            "technology": technology_weight,
        },
    )
