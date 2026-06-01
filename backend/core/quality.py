"""
Quality evaluation for LLM stage outputs.
Used by self-correction loops to decide if a result needs retry.
"""

import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

VALID_BANDS = {"XS", "S", "M", "L", "XL"}
VALID_DECISIONS = {"QUICK_WIN", "STRATEGIC", "HOLD", "DO_NOT_MIGRATE"}


class QualityReport(BaseModel):
    stage: str
    passed: bool
    confidence: str  # HIGH | MEDIUM | LOW
    issues: list[str]
    retry_hint: str | None = None  # hint injected into retry prompt


class QualityEvaluator:
    """Evaluates LLM stage outputs for correctness. Returns QualityReport."""

    def evaluate_s1(self, result: dict) -> QualityReport:
        issues = []
        for field in ("technical_feasibility", "migration_effort", "platform_suitability", "risk"):
            if not isinstance(result.get(field), int):
                issues.append(f"Missing or non-integer field: {field}")
        decision = result.get("migration_decision", "")
        if decision not in VALID_DECISIONS:
            issues.append(f"Invalid migration_decision: '{decision}'")
        if not result.get("analysis"):
            issues.append("Missing analysis text")
        passed = len(issues) == 0
        hint = f"Fix these issues: {'; '.join(issues)}" if issues else None
        return QualityReport(
            stage="s1",
            passed=passed,
            confidence="HIGH" if passed else "LOW",
            issues=issues,
            retry_hint=hint,
        )

    def evaluate_s2(self, result: dict) -> QualityReport:
        issues = []
        required_bands = ("activities", "business_rules", "layouts", "interfaces", "technology")
        for attr in required_bands:
            val = result.get(attr)
            if val not in VALID_BANDS:
                issues.append(f"Invalid band for '{attr}': '{val}'. Must be XS/S/M/L/XL")
        passed = len(issues) == 0
        hint = f"Fix band values: {'; '.join(issues)}" if issues else None
        return QualityReport(
            stage="s2",
            passed=passed,
            confidence="HIGH" if passed else "LOW",
            issues=issues,
            retry_hint=hint,
        )

    def evaluate_s4(self, result: dict) -> QualityReport:
        issues = []
        features = result.get("features", [])
        if not isinstance(features, list) or len(features) == 0:
            issues.append("No features extracted — 'features' must be a non-empty list")
        else:
            for i, f in enumerate(features[:3]):  # spot-check first 3
                if not isinstance(f, dict) or not f.get("name"):
                    issues.append(f"Feature {i} missing required 'name' field")
                if f.get("size") not in VALID_BANDS:
                    issues.append(f"Feature {i} has invalid size: '{f.get('size')}'")
        passed = len(issues) == 0
        hint = f"Fix features list: {'; '.join(issues)}" if issues else None
        return QualityReport(
            stage="s4",
            passed=passed,
            confidence="HIGH" if passed else "LOW",
            issues=issues,
            retry_hint=hint,
        )
