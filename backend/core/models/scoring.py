"""
Data models for complexity scoring and band-based classification.

Defines models for attribute band inputs, scoring results, and weight matrix structure.
Used throughout Stage 2 (Complexity Assessment) workflow for deterministic scoring.

Key models:
- AttributeBands: Five attribute bands without source tags (pure input)
- AttributeBandsWithSource: Bands with source tracking (ai_extracted, manual, corrected, etc.)
- ScoringResult: Output from deterministic scorer (score, complexity, effort)
- WeightMatrix: Band-to-weight mapping loaded from weight_matrix.json

Type aliases:
- Band: Literal band values "XS" | "S" | "M" | "L" | "XL"
- ComplexityClass: Final classification "XS" | "S" | "M" | "L" | "XL"
- InputSource: Tracking tag for data provenance across stages
"""

from typing import Literal

from pydantic import BaseModel, Field

# Type aliases for band-based scoring domain
Band = Literal["XS", "S", "M", "L", "XL"]
ComplexityClass = Literal["XS", "S", "M", "L", "XL"]
InputSource = Literal[
    "ai_extracted", "manual", "corrected", "from_s1", "from_s2", "from_s3", "imported"
]


class AttributeBands(BaseModel):
    """
    Five attribute bands for complexity scoring (without source tracking).

    Used as pure input model when source tags are not needed. Each attribute
    maps to a band (XS/S/M/L/XL) which is then converted to weight via weight matrix.
    """

    activities: Band = Field(..., description="Process activities count band (XS/S/M/L/XL)")
    business_rules: Band = Field(..., description="Business rules complexity band")
    layouts: Band = Field(..., description="Digital layouts/templates count band")
    interfaces: Band = Field(..., description="Target system interfaces count band")
    technology: Band = Field(..., description="Technology complexity band")


class AttributeBandsWithSource(BaseModel):
    """
    Five attribute bands with source tracking for data provenance.

    Extends AttributeBands with source tags for each attribute. Source tags track
    how the band value was obtained (ai_extracted, manual, corrected, from_s2, etc.)
    for audit trail and staleness detection.
    """

    activities: Band = Field(..., description="Process activities count band")
    activities_source: InputSource = Field(
        default="manual", description="Source of activities band value"
    )
    business_rules: Band = Field(..., description="Business rules complexity band")
    business_rules_source: InputSource = Field(
        default="manual", description="Source of business_rules band value"
    )
    layouts: Band = Field(..., description="Digital layouts/templates count band")
    layouts_source: InputSource = Field(
        default="manual", description="Source of layouts band value"
    )
    interfaces: Band = Field(..., description="Target system interfaces count band")
    interfaces_source: InputSource = Field(
        default="manual", description="Source of interfaces band value"
    )
    technology: Band = Field(..., description="Technology complexity band")
    technology_source: InputSource = Field(
        default="manual", description="Source of technology band value"
    )


class ScoringResult(BaseModel):
    """
    Output from deterministic complexity scorer.

    Contains total score (sum of attribute weights), final complexity class,
    effort range estimates, and individual attribute weights for transparency.
    """

    total_score: int = Field(..., description="Sum of all attribute weights (7-28 range)")
    complexity_class: ComplexityClass = Field(..., description="Final classification (XS/S/M/L/XL)")
    effort_min_weeks: int = Field(..., description="Minimum effort estimate in weeks")
    effort_max_weeks: int = Field(..., description="Maximum effort estimate in weeks")
    attribute_weights: dict[str, int] = Field(
        ...,
        description="Individual weights by attribute (activities, business_rules, layouts, interfaces, technology)",
    )


class WeightMatrix(BaseModel):
    """
    Weight matrix structure loaded from weight_matrix.json.

    Maps each attribute and band combination to a numeric weight. Used by
    deterministic scorer to convert band assignments to point weights.

    Structure:
    - activities: {XS: 2, S: 2, M: 4, L: 6, XL: 8}
    - business_rules: {XS: 2, S: 2, M: 4, L: 6, XL: 8}
    - layouts: {XS: 1, S: 1, M: 2, L: 3, XL: 4}
    - interfaces: {XS: 1, S: 1, M: 2, L: 3, XL: 4}
    - technology: {XS: 1, S: 1, M: 2, L: 3, XL: 4}
    """

    activities: dict[Band, int] = Field(..., description="Activities band-to-weight mapping")
    business_rules: dict[Band, int] = Field(
        ..., description="Business rules band-to-weight mapping"
    )
    layouts: dict[Band, int] = Field(..., description="Layouts band-to-weight mapping")
    interfaces: dict[Band, int] = Field(..., description="Interfaces band-to-weight mapping")
    technology: dict[Band, int] = Field(..., description="Technology band-to-weight mapping")
