"""
Complexity agent — deterministic scoring pipeline.
Calls four tools in sequence: attribute_scorer → weighted_calculator → classifier_tool → effort_table_tool.
Zero LLM calls.
"""
import logging
from core.models.scoring import AttributeBands, ScoringResult
from tools.attribute_scorer import score_attributes
from tools.weighted_calculator import calculate_total
from tools.classifier_tool import classify_complexity
from tools.effort_table_tool import lookup_effort

logger = logging.getLogger(__name__)


def run_complexity_scoring(bands: AttributeBands) -> ScoringResult:
    """
    Run deterministic complexity scoring pipeline.
    Entry point for complexity agent.

    Steps:
    1. Score attributes (band → weights)
    2. Calculate total score
    3. Classify complexity
    4. Look up effort

    Args:
        bands: AttributeBands with XS/S/M/L/XL values

    Returns:
        ScoringResult with all computed fields

    Raises:
        ScoringValidationError: If scoring logic fails
    """
    logger.info(f"Starting complexity scoring for bands: {bands.model_dump()}")

    # Step 1: Score attributes
    score_result = score_attributes(bands)
    logger.info(f"Attribute weights: {score_result.attribute_weights}")

    # Step 2: Calculate total
    total_result = calculate_total(score_result.attribute_weights)
    total_score = total_result.total_score
    logger.info(f"Total score: {total_score}")

    # Step 3: Classify complexity
    classification_result = classify_complexity(total_score, bands)
    complexity_class = classification_result.complexity_class
    logger.info(f"Complexity class: {complexity_class}")

    # Step 4: Look up effort
    effort_result = lookup_effort(complexity_class)
    logger.info(f"Effort: {effort_result.min_weeks}-{effort_result.max_weeks} weeks, "
                f"{effort_result.sprint_min}-{effort_result.sprint_max} sprints")

    # Assemble final result
    return ScoringResult(
        total_score=total_score,
        complexity_class=complexity_class,
        effort_min_weeks=effort_result.min_weeks,
        effort_max_weeks=effort_result.max_weeks,
        attribute_weights=score_result.attribute_weights,
    )
