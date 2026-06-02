"""
Sprint assignment tool — deterministic bin-packing with dependency ordering.
Zero LLM. Pure Python algorithm.
"""

import logging

from pydantic import BaseModel, Field

from core.exceptions import ScoringValidationError

logger = logging.getLogger(__name__)

SIZE_POINTS = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}


class Feature(BaseModel):
    name: str
    description: str
    size: str = Field(..., pattern="^(XS|S|M|L|XL)$")
    dependencies: list[str] = Field(default_factory=list)

    @property
    def points(self) -> int:
        return SIZE_POINTS[self.size]


class SprintPlan(BaseModel):
    feature: Feature
    sprint_number: int


class SprintAssignmentResult(BaseModel):
    sprint_plans: list[SprintPlan]
    sprint_summaries: list[dict]  # {sprint_number, features, total_points}
    total_points: int
    warnings: list[str] = Field(default_factory=list)


def topological_sort(features: list[Feature]) -> list[Feature]:
    """
    Sort features by dependencies using Kahn's algorithm.
    Returns sorted list where dependencies come before dependents.
    Raises ScoringValidationError on circular dependencies.
    """
    # Build adjacency list and in-degree map
    feature_map = {f.name: f for f in features}
    in_degree = {f.name: 0 for f in features}
    adj_list = {f.name: [] for f in features}

    for feature in features:
        for dep in feature.dependencies:
            if dep not in feature_map:
                raise ScoringValidationError(f"Feature '{feature.name}' depends on unknown feature '{dep}'")
            adj_list[dep].append(feature.name)
            in_degree[feature.name] += 1

    # Kahn's algorithm
    queue = [name for name, degree in in_degree.items() if degree == 0]
    sorted_names = []

    while queue:
        current = queue.pop(0)
        sorted_names.append(current)

        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_names) != len(features):
        raise ScoringValidationError("Circular dependency detected in features")

    return [feature_map[name] for name in sorted_names]


def assign_sprints(features: list[Feature], sprint_count: int, sprint_capacity: int = 8) -> SprintAssignmentResult:
    """
    Deterministic bin-packing with dependency ordering.

    Algorithm:
    1. Topological sort features by dependencies
    2. Greedy bin-pack into sprints respecting capacity
    3. A feature can only be assigned to a sprint if all its dependencies
       are already assigned to earlier sprints

    Args:
        features: List of features to assign
        sprint_count: Target number of sprints
        sprint_capacity: Story points per sprint (default 8)

    Returns:
        SprintAssignmentResult with sprint assignments and summaries

    Raises:
        ScoringValidationError: If features cannot fit or have circular deps
    """
    if not features:
        return SprintAssignmentResult(sprint_plans=[], sprint_summaries=[], total_points=0)

    # Sort by dependencies first
    sorted_features = topological_sort(features)

    # Track which sprint each feature is assigned to
    feature_sprint_map = {}
    sprints = [[] for _ in range(sprint_count)]
    sprint_points = [0] * sprint_count
    warnings = []

    for feature in sorted_features:
        # Find earliest sprint where:
        # 1. All dependencies are in earlier sprints
        # 2. Capacity is available
        min_sprint = 0

        # Ensure dependencies are satisfied
        for dep_name in feature.dependencies:
            if dep_name in feature_sprint_map:
                dep_sprint = feature_sprint_map[dep_name]
                min_sprint = max(min_sprint, dep_sprint + 1)

        # Find first sprint with capacity starting from min_sprint
        assigned = False
        for sprint_idx in range(min_sprint, sprint_count):
            if sprint_points[sprint_idx] + feature.points <= sprint_capacity:
                sprints[sprint_idx].append(feature)
                sprint_points[sprint_idx] += feature.points
                feature_sprint_map[feature.name] = sprint_idx
                assigned = True
                break

        if not assigned:
            # Try to assign anyway to the last sprint (overflow)
            sprints[-1].append(feature)
            sprint_points[-1] += feature.points
            feature_sprint_map[feature.name] = sprint_count - 1
            warnings.append(
                f"Feature '{feature.name}' ({feature.points}pts) overflows sprint capacity. "
                f"Sprint {sprint_count} now has {sprint_points[-1]} points."
            )

    # Build result
    sprint_plans = []
    for sprint_idx, sprint_features in enumerate(sprints):
        for feature in sprint_features:
            sprint_plans.append(SprintPlan(feature=feature, sprint_number=sprint_idx + 1))

    # Build summaries
    sprint_summaries = []
    for sprint_idx in range(sprint_count):
        sprint_summaries.append(
            {
                "sprint_number": sprint_idx + 1,
                "features": [f.name for f in sprints[sprint_idx]],
                "total_points": sprint_points[sprint_idx],
                "capacity": sprint_capacity,
                "utilization": round(sprint_points[sprint_idx] / sprint_capacity * 100, 1)
                if sprint_capacity > 0
                else 0,
            }
        )

    total_points = sum(f.points for f in features)

    logger.info(
        f"Assigned {len(features)} features ({total_points}pts) to {sprint_count} sprints "
        f"(capacity {sprint_capacity}pts each). Warnings: {len(warnings)}"
    )

    return SprintAssignmentResult(
        sprint_plans=sprint_plans, sprint_summaries=sprint_summaries, total_points=total_points, warnings=warnings
    )
