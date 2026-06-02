"""
Stage 2 scoring tests — verify tools and agents work correctly.
"""

from agents.complexity_agent import run_complexity_scoring
from core.models.scoring import AttributeBands
from tools.attribute_scorer import score_attributes
from tools.classifier_tool import classify_complexity
from tools.effort_table_tool import lookup_effort
from tools.weighted_calculator import calculate_total


def test_attribute_scorer():
    """Test attribute scorer returns correct weights."""
    bands = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="L",
        interfaces="S",
        technology="S",
    )

    result = score_attributes(bands)

    assert result.activities_weight == 8
    assert result.business_rules_weight == 8
    assert result.layouts_weight == 3
    assert result.interfaces_weight == 1
    assert result.technology_weight == 1
    assert result.attribute_weights == {
        "activities": 8,
        "business_rules": 8,
        "layouts": 3,
        "interfaces": 1,
        "technology": 1,
    }


def test_weighted_calculator():
    """Test total calculator sums weights correctly."""
    weights = {
        "activities": 8,
        "business_rules": 8,
        "layouts": 3,
        "interfaces": 1,
        "technology": 1,
    }

    result = calculate_total(weights)
    assert result.total_score == 21


def test_classifier():
    """Test classifier maps score to correct complexity class."""
    bands = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="L",
        interfaces="S",
        technology="S",
    )

    result = classify_complexity(21, bands)
    assert result.complexity_class == "L"


def test_classifier_xs_special_case():
    """Test XS special case: max 2 non-XS attributes."""
    bands = AttributeBands(
        activities="S",
        business_rules="XS",
        layouts="XS",
        interfaces="XS",
        technology="XS",
    )

    # Total score would be 2 (S) + 2 (XS) * 4 = 2 + 2 + 1 + 1 + 1 = 7
    # But with special case logic, should be XS
    result = classify_complexity(7, bands)
    # Note: Our XS special case requires at most 2 non-XS attrs
    # This has 1 non-XS (activities=S), so should be XS
    # But total=7 falls in S range naturally, so let's check the implementation
    # Actually the special case is: non_xs_count <= 2 and xs_count >= 3
    # Here: xs_count=4, non_xs_count=1, so is_xs_special=True
    assert result.complexity_class == "XS"


def test_effort_lookup():
    """Test effort lookup returns correct values."""
    result = lookup_effort("L")

    assert result.min_weeks == 12
    assert result.max_weeks == 12
    assert result.sprint_min == 6
    assert result.sprint_max == 6


def test_full_complexity_pipeline():
    """Test full pipeline from bands to scoring result."""
    bands = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="L",
        interfaces="S",
        technology="S",
    )

    result = run_complexity_scoring(bands)

    assert result.total_score == 21
    assert result.complexity_class == "L"
    assert result.effort_min_weeks == 12
    assert result.effort_max_weeks == 12
    assert result.attribute_weights["activities"] == 8
    assert result.attribute_weights["business_rules"] == 8
    assert result.attribute_weights["layouts"] == 3
    assert result.attribute_weights["interfaces"] == 1
    assert result.attribute_weights["technology"] == 1


def test_manual_band_scoring():
    """Test manual band entry (no LLM) produces correct scores."""
    # Test M class
    bands_m = AttributeBands(
        activities="M",
        business_rules="M",
        layouts="S",
        interfaces="S",
        technology="S",
    )

    result_m = run_complexity_scoring(bands_m)
    assert result_m.total_score == 4 + 4 + 1 + 1 + 1  # 11
    assert result_m.complexity_class == "M"
    assert result_m.effort_min_weeks == 10
    assert result_m.effort_max_weeks == 10

    # Test XL class
    bands_xl = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="XL",
        interfaces="L",
        technology="L",
    )

    result_xl = run_complexity_scoring(bands_xl)
    assert result_xl.total_score == 8 + 8 + 4 + 3 + 3  # 26
    assert result_xl.complexity_class == "XL"
    assert result_xl.effort_min_weeks == 16
    assert result_xl.effort_max_weeks == 16
