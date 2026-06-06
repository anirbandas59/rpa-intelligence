"""
Unit tests for Stage 2 LangGraph complexity_assessment agent.

Tests the v2 (LangGraph) path in isolation and compares output
with v1 (legacy) path to ensure equivalence.
"""


from agents.orchestrator import _run_scoring_v1, _run_scoring_v2, assessment_to_scoring_result
from core.constants import ComplexityTier
from core.models.scoring import AttributeBands


def test_langgraph_ground_truth():
    """
    Test LangGraph agent with ground truth inputs.

    Ground truth:
    - Activities: 45 → XL tier → weight 8
    - Business Rules: 5 → XL tier → weight 8
    - Layouts: 5 → L tier → weight 3
    - Interfaces: 2 → S tier → weight 1
    - Technology: 0 → S tier → weight 1
    Total: 21 → L classification
    """
    raw_attributes = {
        "activities": 45,
        "business_rules": 5,
        "layouts": 5,
        "interfaces": 2,
        "technology": 0,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Ground Truth Test",
        rpa_tool="unknown",
        session_id="test_langgraph_ground_truth",
    )

    # Verify total score
    assert result.total_score == 21, f"Expected total 21, got {result.total_score}"

    # Verify complexity tier
    assert result.complexity_tier == ComplexityTier.L, f"Expected L tier, got {result.complexity_tier}"

    # Verify attribute scores
    assert len(result.attribute_scores) == 5, "Should have 5 attribute scores"

    # Verify individual weights
    weights = [s.weight for s in result.attribute_scores]
    assert weights == [8, 8, 3, 1, 1], f"Expected [8,8,3,1,1], got {weights}"


def test_adapter_converts_assessment_to_scoring():
    """Test that adapter function correctly converts AssessmentResult to ScoringResult."""
    raw_attributes = {
        "activities": 15,
        "business_rules": 2,
        "layouts": 2,
        "interfaces": 3,
        "technology": 1,
    }

    assessment = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Adapter Test",
        rpa_tool="unknown",
        session_id="test_adapter",
    )

    scoring = assessment_to_scoring_result(assessment)

    # Verify same total score
    assert scoring.total_score == assessment.total_score

    # Verify same complexity class
    assert scoring.complexity_class == assessment.complexity_tier.value

    # Verify attribute_weights dict built correctly
    assert len(scoring.attribute_weights) == 5
    assert "activities" in scoring.attribute_weights


def test_v1_v2_equivalence():
    """
    Test that v1 (legacy) and v2 (LangGraph) produce equivalent results
    for the same inputs (before LLM reasoning).

    This validates that the deterministic scoring engine is identical.
    """
    # Test case: Medium complexity
    bands = AttributeBands(
        activities="M",
        business_rules="M",
        layouts="M",
        interfaces="M",
        technology="M",
    )

    # Map bands to raw_attributes (use midpoints)
    raw_attributes = {
        "activities": 15,  # M range: 11-20
        "business_rules": 2,  # M tier
        "layouts": 2,  # M range: 2-3
        "interfaces": 3,  # M range: 3-4
        "technology": 1,  # M tier
    }

    # Run v1 (legacy)
    v1_result = _run_scoring_v1(bands)

    # Run v2 (LangGraph)
    v2_assessment = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Equivalence Test",
        rpa_tool="unknown",
        session_id="test_v1_v2_equivalence",
    )

    v2_result = assessment_to_scoring_result(v2_assessment)

    # Verify total scores match
    assert v1_result.total_score == v2_result.total_score, (
        f"v1 total {v1_result.total_score} != v2 total {v2_result.total_score}"
    )

    # Verify complexity class matches
    assert v1_result.complexity_class == v2_result.complexity_class, (
        f"v1 class {v1_result.complexity_class} != v2 class {v2_result.complexity_class}"
    )


def test_langgraph_xs_tier():
    """Test LangGraph agent with XS tier inputs."""
    raw_attributes = {
        "activities": 5,
        "business_rules": 0,
        "layouts": 0,
        "interfaces": 1,
        "technology": 0,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="XS Test",
        rpa_tool="unknown",
        session_id="test_xs",
    )

    # activities=5 (S→2), business_rules=0 (S→2), layouts=0 (M→2), interfaces=1 (S→1), tech=0 (S→1)
    # Total: 2+2+2+1+1 = 8 → S tier (7-8 range)
    assert result.total_score == 8
    assert result.complexity_tier == ComplexityTier.S


def test_langgraph_xl_tier():
    """Test LangGraph agent with XL tier inputs."""
    raw_attributes = {
        "activities": 60,
        "business_rules": 6,
        "layouts": 10,
        "interfaces": 8,
        "technology": 5,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="XL Test",
        rpa_tool="unknown",
        session_id="test_xl",
    )

    # All XL: 8+8+4+4+4 = 28 → XL tier
    assert result.total_score == 28
    assert result.complexity_tier == ComplexityTier.XL


def test_langgraph_confidence_score():
    """Test that LangGraph agent calculates confidence score correctly."""
    # Use ground truth inputs (21 → L tier)
    raw_attributes = {
        "activities": 45,
        "business_rules": 5,
        "layouts": 5,
        "interfaces": 2,
        "technology": 0,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Confidence Test",
        rpa_tool="unknown",
        session_id="test_confidence",
    )

    # L tier is 16-22, score 21 is near top
    # Confidence should be > 0 and <= 1.0
    assert 0.0 < result.confidence_score <= 1.0

    # For score 21 in L tier (16-22):
    # Distance to nearest boundary = min(21-16, 22-21) = min(5, 1) = 1
    # Expected confidence ≈ 0.14 - 0.33 (1 / 7-point range)
    assert 0.1 < result.confidence_score < 0.5


def test_langgraph_tech_lead_review_flag():
    """Test that requires_tech_lead_review is set correctly."""
    # XL tier should trigger tech lead review
    raw_attributes = {
        "activities": 60,
        "business_rules": 6,
        "layouts": 10,
        "interfaces": 8,
        "technology": 5,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Tech Lead Test",
        rpa_tool="unknown",
        session_id="test_tech_lead",
    )

    assert result.requires_tech_lead_review is True, "XL tier should require tech lead review"


def test_langgraph_reasoning_present():
    """Test that LangGraph agent generates reasoning narrative."""
    raw_attributes = {
        "activities": 15,
        "business_rules": 2,
        "layouts": 2,
        "interfaces": 3,
        "technology": 1,
    }

    result = _run_scoring_v2(
        raw_attributes=raw_attributes,
        project_name="Reasoning Test",
        rpa_tool="unknown",
        session_id="test_reasoning",
    )

    # Reasoning should be a non-empty string
    assert result.reasoning, "Reasoning should be present"
    assert len(result.reasoning) > 10, "Reasoning should be substantive"
