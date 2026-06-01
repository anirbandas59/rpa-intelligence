"""
Unit tests for core/quality.py — QualityEvaluator.
"""

import pytest

from core.quality import QualityEvaluator


@pytest.fixture
def evaluator() -> QualityEvaluator:
    return QualityEvaluator()


# ──────────────────────────────────────────────
# evaluate_s1
# ──────────────────────────────────────────────


class TestEvaluateS1:
    def test_valid_result_passes(self, evaluator: QualityEvaluator) -> None:
        result = {
            "technical_feasibility": 35,
            "migration_effort": 20,
            "platform_suitability": 15,
            "risk": 10,
            "migration_decision": "QUICK_WIN",
            "analysis": "This process is straightforward.",
        }
        report = evaluator.evaluate_s1(result)
        assert report.passed is True
        assert report.stage == "s1"
        assert report.confidence == "HIGH"
        assert report.issues == []
        assert report.retry_hint is None

    def test_missing_integer_fields_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "technical_feasibility": "high",  # not int
            "migration_effort": None,  # None
            # platform_suitability missing
            # risk missing
            "migration_decision": "QUICK_WIN",
            "analysis": "Some analysis.",
        }
        report = evaluator.evaluate_s1(result)
        assert report.passed is False
        assert report.confidence == "LOW"
        # Expect issues for technical_feasibility (str, not int), migration_effort (None),
        # platform_suitability (missing), risk (missing)
        assert len(report.issues) >= 3
        assert report.retry_hint is not None
        assert "Fix these issues" in report.retry_hint

    def test_invalid_migration_decision_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "technical_feasibility": 30,
            "migration_effort": 20,
            "platform_suitability": 15,
            "risk": 10,
            "migration_decision": "YES",  # invalid
            "analysis": "Analysis here.",
        }
        report = evaluator.evaluate_s1(result)
        assert report.passed is False
        assert any("migration_decision" in issue for issue in report.issues)

    def test_missing_analysis_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "technical_feasibility": 30,
            "migration_effort": 20,
            "platform_suitability": 15,
            "risk": 10,
            "migration_decision": "HOLD",
            "analysis": "",  # empty string is falsy
        }
        report = evaluator.evaluate_s1(result)
        assert report.passed is False
        assert any("analysis" in issue.lower() for issue in report.issues)

    def test_all_valid_decisions_pass(self, evaluator: QualityEvaluator) -> None:
        for decision in ("QUICK_WIN", "STRATEGIC", "HOLD", "DO_NOT_MIGRATE"):
            result = {
                "technical_feasibility": 30,
                "migration_effort": 20,
                "platform_suitability": 15,
                "risk": 10,
                "migration_decision": decision,
                "analysis": "Valid.",
            }
            report = evaluator.evaluate_s1(result)
            assert report.passed is True, f"Decision {decision} should pass"


# ──────────────────────────────────────────────
# evaluate_s2
# ──────────────────────────────────────────────


class TestEvaluateS2:
    def test_all_valid_bands_pass(self, evaluator: QualityEvaluator) -> None:
        result = {
            "activities": "M",
            "business_rules": "L",
            "layouts": "S",
            "interfaces": "XS",
            "technology": "XL",
        }
        report = evaluator.evaluate_s2(result)
        assert report.passed is True
        assert report.stage == "s2"
        assert report.confidence == "HIGH"
        assert report.issues == []
        assert report.retry_hint is None

    def test_invalid_band_value_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "activities": "MEDIUM",  # invalid — must be XS/S/M/L/XL
            "business_rules": "L",
            "layouts": "S",
            "interfaces": "XS",
            "technology": "XL",
        }
        report = evaluator.evaluate_s2(result)
        assert report.passed is False
        assert report.confidence == "LOW"
        assert len(report.issues) == 1
        assert "activities" in report.issues[0]
        assert "MEDIUM" in report.issues[0]
        assert report.retry_hint is not None
        assert "Fix band values" in report.retry_hint

    def test_multiple_invalid_bands_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "activities": "big",
            "business_rules": None,
            "layouts": "S",
            "interfaces": "XS",
            "technology": "XL",
        }
        report = evaluator.evaluate_s2(result)
        assert report.passed is False
        assert len(report.issues) == 2

    def test_missing_band_key_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "activities": "M",
            # business_rules missing
            "layouts": "S",
            "interfaces": "XS",
            "technology": "XL",
        }
        report = evaluator.evaluate_s2(result)
        assert report.passed is False
        assert any("business_rules" in issue for issue in report.issues)

    @pytest.mark.parametrize("band", ["XS", "S", "M", "L", "XL"])
    def test_each_valid_band_passes(self, evaluator: QualityEvaluator, band: str) -> None:
        result = {
            "activities": band,
            "business_rules": band,
            "layouts": band,
            "interfaces": band,
            "technology": band,
        }
        report = evaluator.evaluate_s2(result)
        assert report.passed is True


# ──────────────────────────────────────────────
# evaluate_s4
# ──────────────────────────────────────────────


class TestEvaluateS4:
    def test_valid_features_pass(self, evaluator: QualityEvaluator) -> None:
        result = {
            "features": [
                {"name": "Login Automation", "size": "S", "description": "Automate login"},
                {"name": "Data Extraction", "size": "M", "description": "Extract rows"},
                {"name": "Report Generation", "size": "L", "description": "Generate PDF"},
            ]
        }
        report = evaluator.evaluate_s4(result)
        assert report.passed is True
        assert report.stage == "s4"
        assert report.confidence == "HIGH"
        assert report.issues == []
        assert report.retry_hint is None

    def test_empty_features_fails(self, evaluator: QualityEvaluator) -> None:
        result = {"features": []}
        report = evaluator.evaluate_s4(result)
        assert report.passed is False
        assert report.confidence == "LOW"
        assert len(report.issues) == 1
        assert "non-empty list" in report.issues[0]
        assert report.retry_hint is not None
        assert "Fix features list" in report.retry_hint

    def test_missing_features_key_fails(self, evaluator: QualityEvaluator) -> None:
        result = {}
        report = evaluator.evaluate_s4(result)
        assert report.passed is False
        assert len(report.issues) == 1

    def test_feature_missing_name_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "features": [
                {"size": "S", "description": "No name here"},
            ]
        }
        report = evaluator.evaluate_s4(result)
        assert report.passed is False
        assert any("name" in issue for issue in report.issues)

    def test_feature_invalid_size_fails(self, evaluator: QualityEvaluator) -> None:
        result = {
            "features": [
                {"name": "Feature A", "size": "LARGE", "description": "Invalid size"},
            ]
        }
        report = evaluator.evaluate_s4(result)
        assert report.passed is False
        assert any("size" in issue for issue in report.issues)

    def test_only_first_three_features_spot_checked(self, evaluator: QualityEvaluator) -> None:
        """Features beyond index 2 are not checked by the evaluator."""
        result = {
            "features": [
                {"name": "F1", "size": "S", "description": "ok"},
                {"name": "F2", "size": "M", "description": "ok"},
                {"name": "F3", "size": "L", "description": "ok"},
                # index 3 and beyond — invalid but not checked
                {"size": "INVALID"},
                {},
            ]
        }
        report = evaluator.evaluate_s4(result)
        assert report.passed is True
