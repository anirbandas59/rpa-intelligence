"""
Ground truth test for complexity scoring engine.

This test verifies that the deterministic scoring logic produces
the expected classification for a known input combination.

Ground Truth (from CLAUDE.md):
- Activities: 41-60+ (XL tier) → weight 8
- Business Rules: 5-6+ (XL tier) → weight 8
- Layouts: 4-6 (L tier) → weight 3
- Interfaces: 2 (S tier) → weight 1
- Technology: 0 (S tier) → weight 1
- Total: 8 + 8 + 3 + 1 + 1 = 21
- Classification: L (range 16-22)

This test MUST PASS before any phase is considered complete.
"""

from core.constants import ComplexityTier
from core.scoring.classifier import classify, get_confidence_score
from core.scoring.weight_matrix import get_weight_by_id, map_value_to_tier


class TestGroundTruthScoring:
    """Ground truth validation for the scoring engine."""

    def test_tier_mapping_ground_truth(self):
        """Verify raw values map to correct tiers per ground truth."""
        # Activities: 41-60+ → XL
        assert map_value_to_tier(1, 45) == ComplexityTier.XL

        # Business Rules: 5-6+ → XL
        assert map_value_to_tier(2, 5) == ComplexityTier.XL

        # Layouts: 4-6 → L
        assert map_value_to_tier(3, 5) == ComplexityTier.L

        # Interfaces: 2 → S
        assert map_value_to_tier(4, 2) == ComplexityTier.S

        # Technology: 0 → S
        assert map_value_to_tier(5, 0) == ComplexityTier.S

    def test_weight_lookup_ground_truth(self):
        """Verify tier-to-weight mapping per ground truth."""
        # Activities XL → 8
        assert get_weight_by_id(1, ComplexityTier.XL) == 8

        # Business Rules XL → 8
        assert get_weight_by_id(2, ComplexityTier.XL) == 8

        # Layouts L → 3
        assert get_weight_by_id(3, ComplexityTier.L) == 3

        # Interfaces S → 1
        assert get_weight_by_id(4, ComplexityTier.S) == 1

        # Technology S → 1
        assert get_weight_by_id(5, ComplexityTier.S) == 1

    def test_total_score_ground_truth(self):
        """Verify total score calculation per ground truth."""
        # Get weights for each attribute
        activities_weight = get_weight_by_id(1, ComplexityTier.XL)
        business_rules_weight = get_weight_by_id(2, ComplexityTier.XL)
        layouts_weight = get_weight_by_id(3, ComplexityTier.L)
        interfaces_weight = get_weight_by_id(4, ComplexityTier.S)
        technology_weight = get_weight_by_id(5, ComplexityTier.S)

        total = (
            activities_weight
            + business_rules_weight
            + layouts_weight
            + interfaces_weight
            + technology_weight
        )

        assert total == 21, f"Expected total score of 21, got {total}"

    def test_classification_ground_truth(self):
        """Verify final classification per ground truth."""
        total_score = 21
        complexity_class = classify(total_score, is_xs_special_case=False)

        assert complexity_class == "L", (
            f"Expected L classification for score 21, got {complexity_class}"
        )

    def test_confidence_score_calculation(self):
        """Verify confidence score for ground truth classification."""
        total_score = 21
        tier = ComplexityTier.L

        confidence = get_confidence_score(total_score, tier)

        # L tier range is 16-22 (width of 6)
        # Score 21 is 5 from min (16), 1 from max (22)
        # Distance from edge = min(5, 1) = 1
        # Confidence = 1 / (6/2) = 1 / 3 = 0.33
        assert confidence == 0.33, (
            f"Expected confidence ~0.33 for score 21 in L tier, got {confidence}"
        )

    def test_end_to_end_ground_truth(self):
        """End-to-end test: raw values → tiers → weights → total → classification."""
        # Step 1: Map raw values to tiers
        activities_tier = map_value_to_tier(1, 45)
        business_rules_tier = map_value_to_tier(2, 5)
        layouts_tier = map_value_to_tier(3, 5)
        interfaces_tier = map_value_to_tier(4, 2)
        technology_tier = map_value_to_tier(5, 0)

        # Step 2: Get weights for each tier
        weights = [
            get_weight_by_id(1, activities_tier),
            get_weight_by_id(2, business_rules_tier),
            get_weight_by_id(3, layouts_tier),
            get_weight_by_id(4, interfaces_tier),
            get_weight_by_id(5, technology_tier),
        ]

        # Step 3: Calculate total
        total = sum(weights)

        # Step 4: Classify
        complexity_class = classify(total, is_xs_special_case=False)

        # Step 5: Calculate confidence
        tier_enum = ComplexityTier.L  # We know it should be L
        confidence = get_confidence_score(total, tier_enum)

        # Verify all steps
        assert activities_tier == ComplexityTier.XL
        assert business_rules_tier == ComplexityTier.XL
        assert layouts_tier == ComplexityTier.L
        assert interfaces_tier == ComplexityTier.S
        assert technology_tier == ComplexityTier.S
        assert weights == [8, 8, 3, 1, 1]
        assert total == 21
        assert complexity_class == "L"
        assert confidence == 0.33


class TestTierRangeBoundaries:
    """Test tier classification boundaries."""

    def test_tier_boundaries(self):
        """Verify all tier boundaries are correct."""
        # XS: 0-6 (special case, usually requires is_xs_special_case=True)
        # S: 7-8
        assert classify(7) == "S"
        assert classify(8) == "S"

        # M: 9-15
        assert classify(9) == "M"
        assert classify(15) == "M"

        # L: 16-22
        assert classify(16) == "L"
        assert classify(22) == "L"

        # XL: 23-28
        assert classify(23) == "XL"
        assert classify(28) == "XL"

    def test_complexity_tier_enum_methods(self):
        """Verify ComplexityTier enum helper methods."""
        # min_score() and max_score()
        assert ComplexityTier.XS.min_score() == 0
        assert ComplexityTier.XS.max_score() == 6
        assert ComplexityTier.S.min_score() == 7
        assert ComplexityTier.S.max_score() == 8
        assert ComplexityTier.M.min_score() == 9
        assert ComplexityTier.M.max_score() == 15
        assert ComplexityTier.L.min_score() == 16
        assert ComplexityTier.L.max_score() == 22
        assert ComplexityTier.XL.min_score() == 23
        assert ComplexityTier.XL.max_score() == 28

        # numeric_rank()
        assert ComplexityTier.XS.numeric_rank() == 1
        assert ComplexityTier.S.numeric_rank() == 2
        assert ComplexityTier.M.numeric_rank() == 3
        assert ComplexityTier.L.numeric_rank() == 4
        assert ComplexityTier.XL.numeric_rank() == 5

        # is_above()
        assert ComplexityTier.XL.is_above(ComplexityTier.L)
        assert ComplexityTier.L.is_above(ComplexityTier.M)
        assert not ComplexityTier.S.is_above(ComplexityTier.M)
