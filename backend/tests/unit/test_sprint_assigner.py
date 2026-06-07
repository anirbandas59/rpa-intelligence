"""
Unit tests for sprint assigner tool — deterministic bin-packing.
"""

import pytest

from core.exceptions import ScoringValidationError
from tools.sprint_assigner import Feature, assign_sprints, topological_sort


def test_topological_sort_no_dependencies():
    """Test sorting features with no dependencies."""
    features = [
        Feature(name="feature-a", description="A", size="M"),
        Feature(name="feature-b", description="B", size="S"),
        Feature(name="feature-c", description="C", size="L"),
    ]

    sorted_features = topological_sort(features)
    assert len(sorted_features) == 3
    # With no dependencies, original order should be preserved
    assert [f.name for f in sorted_features] == ["feature-a", "feature-b", "feature-c"]


def test_topological_sort_with_dependencies():
    """Test sorting features with dependency chains."""
    features = [
        Feature(
            name="feature-c", description="C", size="M", dependencies=["feature-a", "feature-b"]
        ),
        Feature(name="feature-b", description="B", size="S", dependencies=["feature-a"]),
        Feature(name="feature-a", description="A", size="S", dependencies=[]),
    ]

    sorted_features = topological_sort(features)
    names = [f.name for f in sorted_features]

    # feature-a must come first, feature-b before feature-c
    assert names.index("feature-a") < names.index("feature-b")
    assert names.index("feature-b") < names.index("feature-c")


def test_topological_sort_circular_dependency():
    """Test that circular dependencies are detected."""
    features = [
        Feature(name="feature-a", description="A", size="M", dependencies=["feature-b"]),
        Feature(name="feature-b", description="B", size="S", dependencies=["feature-a"]),
    ]

    with pytest.raises(ScoringValidationError, match="Circular dependency"):
        topological_sort(features)


def test_topological_sort_missing_dependency():
    """Test that missing dependencies are detected."""
    features = [
        Feature(name="feature-a", description="A", size="M", dependencies=["feature-x"]),
    ]

    with pytest.raises(ScoringValidationError, match="unknown feature"):
        topological_sort(features)


def test_assign_sprints_simple():
    """Test basic sprint assignment."""
    features = [
        Feature(name="setup", description="Setup", size="S"),  # 2pts
        Feature(name="workflow", description="Workflow", size="M"),  # 3pts
        Feature(name="testing", description="Testing", size="S"),  # 2pts
    ]

    result = assign_sprints(features, sprint_count=1, sprint_capacity=8)

    assert result.total_points == 7
    assert len(result.sprint_plans) == 3
    assert all(sp.sprint_number == 1 for sp in result.sprint_plans)
    assert len(result.sprint_summaries) == 1
    assert result.sprint_summaries[0]["total_points"] == 7


def test_assign_sprints_multiple_sprints():
    """Test assignment across multiple sprints."""
    features = [
        Feature(name="f1", description="F1", size="L"),  # 5pts
        Feature(name="f2", description="F2", size="M"),  # 3pts
        Feature(name="f3", description="F3", size="M"),  # 3pts
        Feature(name="f4", description="F4", size="S"),  # 2pts
    ]

    result = assign_sprints(features, sprint_count=2, sprint_capacity=8)

    assert result.total_points == 13
    assert len(result.sprint_plans) == 4

    # Check sprint 1 should have f1 (5) + f2 (3) = 8pts
    sprint1_plans = [sp for sp in result.sprint_plans if sp.sprint_number == 1]
    sprint1_points = sum(sp.feature.points for sp in sprint1_plans)
    assert sprint1_points == 8

    # Sprint 2 should have f3 (3) + f4 (2) = 5pts
    sprint2_plans = [sp for sp in result.sprint_plans if sp.sprint_number == 2]
    sprint2_points = sum(sp.feature.points for sp in sprint2_plans)
    assert sprint2_points == 5


def test_assign_sprints_with_dependencies():
    """Test that dependencies are respected in sprint assignment."""
    features = [
        Feature(name="foundation", description="Foundation", size="M", dependencies=[]),
        Feature(name="api", description="API", size="M", dependencies=["foundation"]),
        Feature(name="ui", description="UI", size="M", dependencies=["api"]),
    ]

    result = assign_sprints(features, sprint_count=3, sprint_capacity=8)

    # Each feature should be in a different sprint due to dependencies
    plans_by_name = {sp.feature.name: sp.sprint_number for sp in result.sprint_plans}

    assert plans_by_name["foundation"] < plans_by_name["api"]
    assert plans_by_name["api"] < plans_by_name["ui"]


def test_assign_sprints_overflow():
    """Test handling when features overflow sprint capacity."""
    features = [
        Feature(name="f1", description="F1", size="XL"),  # 8pts
        Feature(name="f2", description="F2", size="L"),  # 5pts
    ]

    result = assign_sprints(features, sprint_count=1, sprint_capacity=8)

    # Should warn about overflow
    assert len(result.warnings) > 0
    assert "overflow" in result.warnings[0].lower()

    # Both features should still be assigned
    assert len(result.sprint_plans) == 2


def test_assign_sprints_empty():
    """Test assignment with no features."""
    result = assign_sprints([], sprint_count=2, sprint_capacity=8)

    assert result.total_points == 0
    assert len(result.sprint_plans) == 0
    assert len(result.sprint_summaries) == 0


def test_size_points_mapping():
    """Test that size to points mapping is correct."""
    features = [
        Feature(name="xs", description="XS", size="XS"),  # 1
        Feature(name="s", description="S", size="S"),  # 2
        Feature(name="m", description="M", size="M"),  # 3
        Feature(name="l", description="L", size="L"),  # 5
        Feature(name="xl", description="XL", size="XL"),  # 8
    ]

    result = assign_sprints(features, sprint_count=3, sprint_capacity=8)

    # Total: 1 + 2 + 3 + 5 + 8 = 19
    assert result.total_points == 19


def test_sprint_summaries():
    """Test that sprint summaries are correctly generated."""
    features = [
        Feature(name="f1", description="F1", size="L"),  # 5pts
        Feature(name="f2", description="F2", size="M"),  # 3pts
        Feature(name="f3", description="F3", size="S"),  # 2pts
    ]

    result = assign_sprints(features, sprint_count=2, sprint_capacity=8)

    assert len(result.sprint_summaries) == 2

    # Sprint 1 should have 2 features (5+3=8pts)
    summary1 = result.sprint_summaries[0]
    assert summary1["sprint_number"] == 1
    assert summary1["total_points"] == 8
    assert len(summary1["features"]) == 2
    assert summary1["utilization"] == 100.0  # 8/8 * 100

    # Sprint 2 should have 1 feature (2pts)
    summary2 = result.sprint_summaries[1]
    assert summary2["sprint_number"] == 2
    assert summary2["total_points"] == 2
    assert len(summary2["features"]) == 1
    assert summary2["utilization"] == 25.0  # 2/8 * 100
