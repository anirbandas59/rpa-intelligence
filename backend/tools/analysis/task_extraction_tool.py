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


def validate_hour_sum(
    result: TaskExtractionResult, budget: float, tolerance: float = 0.5
) -> tuple[bool, str]:
    """
    Verify that sum of non-full-reuse step hours matches budget within tolerance.

    Args:
        result: Parsed task extraction result
        budget: Target effort hours
        tolerance: Acceptable deviation (hours)

    Returns:
        Tuple of (is_valid: bool, error_message: str)
        error_message is empty string if valid
    """
    # Recalculate net hours (don't trust LLM's total_net_hours field)
    actual_sum = 0.0
    step_count = 0
    reusability_breakdown = {"full": 0, "partial": 0, "none": 0}

    for activity in result.activities:
        for step in activity.steps:
            step_count += 1
            reusability_breakdown[step.reusability] += 1

            # Calculate net hours based on reusability
            if step.reusability == "full":
                net_hours = 0.0
            elif step.reusability == "partial":
                net_hours = step.weight_hours * 0.5
            else:  # none
                net_hours = step.weight_hours

            actual_sum += net_hours

    diff = abs(actual_sum - budget)
    passed = diff <= tolerance

    if not passed:
        error_msg = (
            f"Hour sum validation failed:\n"
            f"  Expected: {budget:.2f}h\n"
            f"  Actual: {actual_sum:.2f}h\n"
            f"  Difference: {diff:.2f}h (tolerance: ±{tolerance:.2f}h)\n"
            f"  Total steps: {step_count}\n"
            f"  Reusability breakdown: {reusability_breakdown}\n"
            f"  Suggestion: Adjust step hours proportionally by {(budget/actual_sum):.3f}x"
        )
        logger.warning(error_msg)
        return False, error_msg

    logger.info(
        f"Hour sum validation passed: {actual_sum:.2f}h within ±{tolerance:.2f}h of {budget:.2f}h"
    )
    return True, ""


def validate_context_relevance(
    result: TaskExtractionResult, process_summary: dict | None
) -> tuple[bool, list[str]]:
    """
    Validate that extracted activities align with process context from S2.

    Args:
        result: Parsed task extraction result
        process_summary: Stage 2 process summary dict (optional)

    Returns:
        Tuple of (is_valid: bool, errors: list[str])
    """
    if not process_summary:
        # Skip validation if no process summary available
        return True, []

    errors = []

    # Check 1: Context relevance (web activities in non-web processes)
    key_applications = process_summary.get("key_applications", [])
    key_technologies = process_summary.get("key_additional_technologies", [])

    has_web = any(
        "browser" in app.lower()
        or "web" in app.lower()
        or "chrome" in app.lower()
        or "http" in tech.lower()
        for app in key_applications
        for tech in key_technologies
    )

    if not has_web:
        web_keywords = ["login to web", "navigate web", "browser", "url", "http://", "https://"]
        for activity in result.activities:
            activity_name = activity.name.lower()
            for step in activity.steps:
                step_desc = step.description.lower()
                matched_keyword = next(
                    (kw for kw in web_keywords if kw in activity_name or kw in step_desc), None
                )
                if matched_keyword:
                    errors.append(
                        f"Context mismatch: Found web-related step '{step.description[:80]}' "
                        f"(keyword: '{matched_keyword}') but process has no web applications. "
                        f"Applications: {', '.join(key_applications[:5])}"
                    )
                    break  # Only report once per activity

    # Check 2: Completeness (key activities represented)
    key_activities = process_summary.get("key_activities", [])
    synthesis_activity_names = [act.name.lower() for act in result.activities]

    missing_activities = []
    for key_act in key_activities[:5]:  # Check first 5 key activities
        key_act_lower = key_act.lower()
        # Check if any synthesis activity is related (substring match)
        if not any(
            key_act_lower in synth_name or synth_name in key_act_lower
            for synth_name in synthesis_activity_names
        ):
            missing_activities.append(key_act)

    if missing_activities:
        errors.append(
            f"Incompleteness: The following key activities from S2 are not represented in task breakdown: "
            f"{', '.join(missing_activities)}. Please add steps for these activities or explain their absence."
        )

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Context relevance validation failed with {len(errors)} errors")
    else:
        logger.info("Context relevance validation passed")

    return is_valid, errors


def validate_reusability_logic(result: TaskExtractionResult) -> tuple[bool, list[str]]:
    """
    Validate that reusability tags are applied correctly.

    Args:
        result: Parsed task extraction result

    Returns:
        Tuple of (is_valid: bool, warnings: list[str])
    """
    warnings = []
    reusability_stats = {"full": 0, "partial": 0, "none": 0}

    for activity in result.activities:
        for step in activity.steps:
            reusability_stats[step.reusability] += 1

            # Check for common patterns that should be reusable
            desc_lower = step.description.lower()

            # "full" should only be genuinely reusable components
            if step.reusability == "full":
                if not any(
                    keyword in desc_lower
                    for keyword in [
                        "login",
                        "authentication",
                        "error handling",
                        "logging",
                        "framework",
                        "wrapper",
                        "utility",
                    ]
                ):
                    warnings.append(
                        f"Questionable 'full' reusability: '{step.description[:80]}' - "
                        f"Only login frameworks, error handling wrappers, and utilities should be 'full'"
                    )

            # Business logic should rarely be "full" reusable
            if step.reusability == "full" and any(
                keyword in desc_lower for keyword in ["validate", "calculate", "process", "transform"]
            ):
                warnings.append(
                    f"Business logic marked as 'full' reusable: '{step.description[:80]}' - "
                    f"Consider 'partial' or 'none' for process-specific logic"
                )

    total_steps = sum(reusability_stats.values())
    if total_steps > 0:
        full_pct = (reusability_stats["full"] / total_steps) * 100
        if full_pct > 30:
            warnings.append(
                f"High 'full' reusability percentage ({full_pct:.1f}%) - "
                f"Most steps should be 'none' (conservative estimate). "
                f"Stats: {reusability_stats}"
            )

    is_valid = len(warnings) == 0

    if warnings:
        logger.warning(f"Reusability validation found {len(warnings)} warnings")
    else:
        logger.info("Reusability validation passed")

    return is_valid, warnings
