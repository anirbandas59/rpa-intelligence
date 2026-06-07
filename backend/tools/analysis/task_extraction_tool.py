"""Task extraction parsing and validation tool."""

import json
import logging

from pydantic import BaseModel, Field

from core.exceptions import ScoringValidationError

logger = logging.getLogger(__name__)


class TaskStep(BaseModel):
    description: str
    weight_hours: float = Field(ge=0)
    reusability: str = Field(pattern="^(full|partial|none)$")


class Activity(BaseModel):
    name: str
    steps: list[TaskStep]


class TaskExtractionResult(BaseModel):
    activities: list[Activity]
    total_net_hours: float
    verification_passed: bool


def parse_task_extraction(raw_json: str) -> TaskExtractionResult:
    """Parse JSON response from task extraction LLM call."""
    try:
        # Strip markdown fences
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # Find JSON object
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON object found in response")

        json_str = cleaned[start_idx:end_idx]
        parsed = json.loads(json_str)

        # Validate structure
        return TaskExtractionResult(**parsed)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse task extraction JSON: {e}")
        raise ScoringValidationError(f"Invalid JSON in task extraction: {e}")
    except Exception as e:
        logger.error(f"Task extraction parsing failed: {e}")
        raise ScoringValidationError(f"Task extraction validation failed: {e}")


def validate_hour_sum(result: TaskExtractionResult, budget: float, tolerance: float = 0.5) -> bool:
    """Verify that sum of non-full-reuse step hours matches budget within tolerance."""
    # Recalculate net hours (don't trust LLM's total_net_hours field)
    actual_sum = 0.0
    for activity in result.activities:
        for step in activity.steps:
            if step.reusability != "full":
                actual_sum += step.weight_hours

    diff = abs(actual_sum - budget)
    passed = diff <= tolerance

    if not passed:
        logger.warning(
            f"Hour sum validation failed: actual={actual_sum:.2f}, "
            f"budget={budget:.2f}, diff={diff:.2f}"
        )

    return passed
