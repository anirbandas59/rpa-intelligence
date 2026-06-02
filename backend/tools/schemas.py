"""
Pydantic schemas for all registered tools.
Input and output models used by the ToolRegistry and orchestrator.
"""

from pydantic import BaseModel

from core.models.scoring import Band, ComplexityClass


# --- run_s1_assessment ---
class S1AssessmentInput(BaseModel):
    use_case_id: str


class S1AssessmentOutput(BaseModel):
    run_id: str
    status: str
    migration_decision: str | None = None
    total_score: int | None = None


# --- run_s2_extraction ---
class S2ExtractionInput(BaseModel):
    use_case_id: str
    document_path: str | None = None
    pasted_text: str | None = None
    manual_bands: dict[str, str] | None = None


class S2ExtractionOutput(BaseModel):
    run_id: str
    status: str
    complexity_class: ComplexityClass | None = None
    total_score: int | None = None


# --- run_s3_timeline ---
class S3TimelineInput(BaseModel):
    use_case_id: str
    effort_weeks: int
    start_date: str  # ISO date string "YYYY-MM-DD"
    complexity_class: ComplexityClass = "M"


class S3TimelineOutput(BaseModel):
    run_id: str
    status: str
    total_weeks: int | None = None
    phase_count: int | None = None


# --- run_s4_tracker ---
class S4TrackerInput(BaseModel):
    use_case_id: str
    sprint_count: int
    sprint_capacity: int = 8


class S4TrackerOutput(BaseModel):
    run_id: str
    status: str
    feature_count: int | None = None
    sprint_count: int | None = None


# --- get_stage_result ---
class GetStageResultInput(BaseModel):
    use_case_id: str
    stage: str  # s1 | s2 | s3 | s4


class GetStageResultOutput(BaseModel):
    run_id: str | None
    status: str  # complete | running | stale | not_run
    result: dict | None = None


# --- update_stage_inputs ---
class UpdateStageInputsInput(BaseModel):
    use_case_id: str
    stage: str
    inputs: dict  # fields to merge into sN_inputs


class UpdateStageInputsOutput(BaseModel):
    updated: bool
    use_case_id: str


# --- calculate_complexity ---
class CalculateComplexityInput(BaseModel):
    activities: Band
    business_rules: Band
    layouts: Band
    interfaces: Band
    technology: Band


class CalculateComplexityOutput(BaseModel):
    total_score: int
    complexity_class: ComplexityClass
    effort_min_weeks: int
    effort_max_weeks: int


# --- check_run_status ---
class CheckRunStatusInput(BaseModel):
    run_id: str


class CheckRunStatusOutput(BaseModel):
    run_id: str
    status: str  # running | complete | failed
    stage: str | None = None


# --- query_similar_use_cases ---
class QuerySimilarInput(BaseModel):
    keywords: list[str]
    limit: int = 3


class QuerySimilarOutput(BaseModel):
    results: list[dict]  # each: {use_case_id, name, stage, summary}
