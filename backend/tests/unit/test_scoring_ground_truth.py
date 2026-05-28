"""
Ground truth test — must pass before any phase is considered complete.
Input:  Activities XL, Business Rules XL, Layouts L, Interfaces S, Technology S
Expected: total=21, class=L
"""
import pytest
from core.scoring.weight_matrix import load_weight_matrix, get_weight
from core.scoring.classifier import classify
from core.scoring.effort_table import get_effort
from core.models.scoring import AttributeBands


def test_ground_truth():
    matrix = load_weight_matrix()
    bands = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="L",
        interfaces="S",
        technology="S",
    )
    total = (
        get_weight(matrix, "activities", bands.activities) +
        get_weight(matrix, "business_rules", bands.business_rules) +
        get_weight(matrix, "layouts", bands.layouts) +
        get_weight(matrix, "interfaces", bands.interfaces) +
        get_weight(matrix, "technology", bands.technology)
    )
    assert total == 21, f"Expected 21, got {total}"
    cls = classify(total)
    assert cls == "L", f"Expected L, got {cls}"
    effort = get_effort(cls)

    # 1 business month = 22 days, 1 business week = 5 days
    assert effort["min_weeks"] == 12
    assert effort["max_weeks"] == 12
    assert effort["sprint_min"] == 6
    assert effort["sprint_max"] == 6


def test_xs_special_case():
    cls = classify(total_score=4, is_xs_special_case=True)
    assert cls == "XS"


def test_classifier_boundaries():
    assert classify(7) == "S"
    assert classify(8) == "S"
    assert classify(9) == "M"
    assert classify(15) == "M"
    assert classify(16) == "L"
    assert classify(22) == "L"
    assert classify(23) == "XL"
    assert classify(28) == "XL"
