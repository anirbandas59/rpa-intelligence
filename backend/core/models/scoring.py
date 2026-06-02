from typing import Literal

from pydantic import BaseModel

Band = Literal["XS", "S", "M", "L", "XL"]
ComplexityClass = Literal["XS", "S", "M", "L", "XL"]
InputSource = Literal["ai_extracted", "manual", "corrected", "from_s1", "from_s2", "from_s3", "imported"]


class AttributeBands(BaseModel):
    activities: Band
    business_rules: Band
    layouts: Band
    interfaces: Band
    technology: Band


class AttributeBandsWithSource(BaseModel):
    activities: Band
    activities_source: InputSource = "manual"
    business_rules: Band
    business_rules_source: InputSource = "manual"
    layouts: Band
    layouts_source: InputSource = "manual"
    interfaces: Band
    interfaces_source: InputSource = "manual"
    technology: Band
    technology_source: InputSource = "manual"


class ScoringResult(BaseModel):
    total_score: int
    complexity_class: ComplexityClass
    effort_min_weeks: int
    effort_max_weeks: int
    attribute_weights: dict[str, int]


class WeightMatrix(BaseModel):
    activities: dict[Band, int]
    business_rules: dict[Band, int]
    layouts: dict[Band, int]
    interfaces: dict[Band, int]
    technology: dict[Band, int]
