"""
Decision derivation utilities for Stage 1 migration assessment.

This module provides the canonical logic for deriving migration_decision
from total_score based on priority bands. Used by both the assessment service
and the manual override endpoint to ensure consistent decision calculation.
"""


def derive_migration_decision(total_score: int) -> str:
    """
    Derive migration decision from total score using priority bands.

    Priority bands (as defined in assessment_prompts.py and CLAUDE.md):
    - QUICK_WIN: 75-100
    - STRATEGIC: 50-74
    - HOLD: 25-49
    - DO_NOT_MIGRATE: 0-24

    Args:
        total_score: Sum of technical_feasibility + migration_effort +
                     platform_suitability + risk (range 0-100)

    Returns:
        One of: "QUICK_WIN", "STRATEGIC", "HOLD", "DO_NOT_MIGRATE"

    Examples:
        >>> derive_migration_decision(85)
        'QUICK_WIN'
        >>> derive_migration_decision(60)
        'STRATEGIC'
        >>> derive_migration_decision(30)
        'HOLD'
        >>> derive_migration_decision(10)
        'DO_NOT_MIGRATE'
    """
    if total_score >= 75:
        return "QUICK_WIN"
    elif total_score >= 50:
        return "STRATEGIC"
    elif total_score >= 25:
        return "HOLD"
    else:
        return "DO_NOT_MIGRATE"
