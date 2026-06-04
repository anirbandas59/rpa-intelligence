"""
Weight matrix for RPA complexity assessment.

This module loads the weight matrix from data/reference/weight_matrix.json
and provides functions to look up weights, map values to tiers, and
check for ceiling violations.

The weight matrix is the single source of truth for all scoring weights
and tier range mappings.
"""

import json
from pathlib import Path

from core.constants import ComplexityTier
from core.exceptions import DocumentProcessingError, ScoringValidationError

# Load weight matrix at module level
_WEIGHT_MATRIX_PATH = (
    Path(__file__).parent.parent.parent / "data" / "reference" / "weight_matrix.json"
)
_MATRIX_CACHE: dict | None = None

# Full weight data cache (includes weight + range for each attribute/tier combo)
_FULL_WEIGHT_DATA: dict | None = None

# Attribute ID to name mapping
_ATTRIBUTE_NAMES = {
    1: "activities",
    2: "business_rules",
    3: "layouts",
    4: "interfaces",
    5: "technology",
}

# Reverse mapping for getting attribute ID from name
_ATTRIBUTE_IDS = {v: k for k, v in _ATTRIBUTE_NAMES.items()}

# XL ceilings for each attribute
_XL_CEILINGS = {
    1: 60,  # Activities
    2: 6,  # Business Rules
    3: 10,  # Layouts
    4: 8,  # Interfaces
    5: 5,  # Technology
}


def load_weight_matrix() -> dict:
    """
    Load raw weight matrix from JSON.

    Returns nested dict keyed by attribute → band → weight int.
    """
    global _MATRIX_CACHE
    if _MATRIX_CACHE is None:
        try:
            with open(_WEIGHT_MATRIX_PATH) as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise DocumentProcessingError(
                f"weight_matrix.json not found at {_WEIGHT_MATRIX_PATH}. "
                f"Run scripts/seed_reference_data.py first."
            ) from e
        # Flatten: {"activities": {"XS": 2, "S": 2, ...}, ...}
        _MATRIX_CACHE = {
            attr: {band: values["weight"] for band, values in bands.items()}
            for attr, bands in data["weights"].items()
        }
    return _MATRIX_CACHE


def load_full_weight_data() -> dict:
    """
    Load complete weight data including ranges and descriptions.

    Returns nested dict: attribute → tier → {"weight": int, "range": str}
    """
    global _FULL_WEIGHT_DATA
    if _FULL_WEIGHT_DATA is None:
        try:
            with open(_WEIGHT_MATRIX_PATH) as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise DocumentProcessingError(
                f"weight_matrix.json not found at {_WEIGHT_MATRIX_PATH}. "
                f"Run scripts/seed_reference_data.py first."
            ) from e
        _FULL_WEIGHT_DATA = data["weights"]

    # Type checker assertion - we know it's not None after the check above
    assert _FULL_WEIGHT_DATA is not None
    return _FULL_WEIGHT_DATA


def get_weight(matrix: dict, attribute: str, band: str) -> int:
    """Get weight from pre-loaded matrix dict (legacy signature).

    Args:
        matrix: Pre-loaded weight matrix dict
        attribute: Attribute name (e.g., "activities")
        band: Tier band (e.g., "XS", "S", "M", "L", "XL")

    Returns:
        Weight value for this attribute-band combination

    Raises:
        ScoringValidationError: If attribute or band is invalid
    """
    attr_weights = matrix.get(attribute)
    if attr_weights is None:
        raise ScoringValidationError(f"Unknown attribute: {attribute}")
    weight = attr_weights.get(band)
    if weight is None:
        raise ScoringValidationError(f"Unknown band '{band}' for attribute '{attribute}'")
    return weight


def get_weight_by_id(attribute_id: int, tier: ComplexityTier) -> int:
    """Get the point weight for an attribute and tier combination.

    This is the new signature matching complexity-agent pattern.

    Args:
        attribute_id: Attribute ID (1-5)
        tier: ComplexityTier enum value

    Returns:
        The point weight for this combination

    Raises:
        ScoringValidationError: If attribute_id or tier is invalid
    """
    if attribute_id not in _ATTRIBUTE_NAMES:
        raise ScoringValidationError(
            f"Invalid attribute_id: {attribute_id}. Must be 1-5.",
            context={"attribute_id": attribute_id},
        )

    if not isinstance(tier, ComplexityTier):
        raise ScoringValidationError(
            f"Invalid tier: {tier}. Must be a ComplexityTier.",
            context={"tier": tier},
        )

    attribute_name = _ATTRIBUTE_NAMES[attribute_id]
    tier_name = tier.value
    full_data = load_full_weight_data()

    try:
        weight_info = full_data[attribute_name][tier_name]
        return weight_info["weight"]
    except (KeyError, TypeError) as e:
        raise ScoringValidationError(
            f"Weight not found for attribute {attribute_id} ({attribute_name}) "
            f"and tier {tier_name}",
            context={"attribute_id": attribute_id, "tier": tier_name},
        ) from e


# COMMENTED OUT: Duplicate get_weight implementation that conflicts with the working
# version above. This version references undefined _WEIGHTS variable and is not used
# by any callers. The working implementation at lines 73-80 accepts (matrix,
# attribute, band) and is used throughout the codebase.
#
# def get_weight(attribute_id: int, tier: ComplexityTier) -> int:
#     """Get the point weight for an attribute and tier combination.
#
#     Args:
#         attribute_id: Attribute ID (1-5)
#         tier: ComplexityTier (XS, S, M, L, XL)
#
#     Returns:
#         The point weight for this combination
#
#     Raises:
#         ScoringValidationError: If attribute_id or tier is invalid
#     """
#     if attribute_id not in _ATTRIBUTE_NAMES:
#         raise ScoringValidationError(
#             f"Invalid attribute_id: {attribute_id}. Must be 1-5.",
#             context={"attribute_id": attribute_id},
#         )
#
#     if not isinstance(tier, ComplexityTier):
#         raise ScoringValidationError(
#             f"Invalid tier: {tier}. Must be a ComplexityTier.",
#             context={"tier": tier},
#         )
#
#     attribute_name = _ATTRIBUTE_NAMES[attribute_id]
#     tier_name = tier.value
#
#     try:
#         weight_info = _WEIGHTS[attribute_name][tier_name]
#         return weight_info["weight"]
#     except (KeyError, TypeError) as e:
#         raise ScoringValidationError(
#             f"Weight not found for attribute {attribute_id} ({attribute_name}) "
#             f"and tier {tier_name}",
#             context={"attribute_id": attribute_id, "tier": tier_name},
#         ) from e


def get_tier_range_description(attribute_id: int, tier: ComplexityTier) -> str:
    """Get the human-readable range description for an attribute-tier pair.

    Args:
        attribute_id: Attribute ID (1-5)
        tier: ComplexityTier (XS, S, M, L, XL)

    Returns:
        The range description (e.g., "41-60 activities")

    Raises:
        ScoringValidationError: If attribute_id or tier is invalid
    """
    if attribute_id not in _ATTRIBUTE_NAMES:
        raise ScoringValidationError(
            f"Invalid attribute_id: {attribute_id}. Must be 1-5.",
            context={"attribute_id": attribute_id},
        )

    if not isinstance(tier, ComplexityTier):
        raise ScoringValidationError(
            f"Invalid tier: {tier}. Must be a ComplexityTier.",
            context={"tier": tier},
        )

    attribute_name = _ATTRIBUTE_NAMES[attribute_id]
    tier_name = tier.value
    full_data = load_full_weight_data()

    try:
        tier_info = full_data[attribute_name][tier_name]
        return tier_info.get("range", "Unknown range")
    except (KeyError, TypeError) as e:
        raise ScoringValidationError(
            f"Range description not found for attribute {attribute_id} "
            f"({attribute_name}) and tier {tier_name}",
            context={"attribute_id": attribute_id, "tier": tier_name},
        ) from e


def get_all_weights() -> dict[str, dict[str, int]]:
    """Get the full weight matrix for inspection.

    Returns:
        Nested dict: attribute_name -> tier_name -> weight value
    """
    full_data = load_full_weight_data()
    result: dict[str, dict[str, int]] = {}
    for attr_name, tiers in full_data.items():
        result[attr_name] = {}
        for tier_name, tier_info in tiers.items():
            result[attr_name][tier_name] = tier_info["weight"]
    return result


def map_value_to_tier(attribute_id: int, raw_value: int) -> ComplexityTier:
    """Map a raw value count to the appropriate ComplexityTier.

    Each attribute has defined ranges that map to specific tiers.
    Values are capped at XL if they exceed the maximum.

    Args:
        attribute_id: Attribute ID (1-5)
        raw_value: The raw count value to map

    Returns:
        The ComplexityTier for this value

    Raises:
        ScoringValidationError: If attribute_id is invalid or raw_value < 0
    """
    if attribute_id not in _ATTRIBUTE_NAMES:
        raise ScoringValidationError(
            f"Invalid attribute_id: {attribute_id}. Must be 1-5.",
            context={"attribute_id": attribute_id},
        )

    if raw_value < 0:
        raise ScoringValidationError(
            f"Invalid raw_value: {raw_value}. Must be >= 0.",
            context={"attribute_id": attribute_id, "raw_value": raw_value},
        )

    # Map based on attribute ID
    if attribute_id == 1:  # Activities
        if raw_value <= 10:
            return ComplexityTier.S
        elif raw_value <= 20:
            return ComplexityTier.M
        elif raw_value <= 40:
            return ComplexityTier.L
        else:  # 41+
            return ComplexityTier.XL

    elif attribute_id == 2:  # Business Rules
        if raw_value == 0:
            return ComplexityTier.S
        elif raw_value <= 2:
            return ComplexityTier.M
        elif raw_value <= 4:
            return ComplexityTier.L
        else:  # 5+
            return ComplexityTier.XL

    elif attribute_id == 3:  # Layouts
        if raw_value == 1:
            return ComplexityTier.S
        elif raw_value <= 3:
            return ComplexityTier.M
        elif raw_value <= 6:
            return ComplexityTier.L
        else:  # 7+
            return ComplexityTier.XL

    elif attribute_id == 4:  # Interfaces
        if raw_value == 0:
            return ComplexityTier.S
        elif raw_value <= 2:
            return ComplexityTier.S
        elif raw_value <= 4:
            return ComplexityTier.M
        elif raw_value <= 6:
            return ComplexityTier.L
        else:  # 7+
            return ComplexityTier.XL

    elif attribute_id == 5:  # Additional Technology
        if raw_value == 0:
            return ComplexityTier.S
        elif raw_value == 1:
            return ComplexityTier.M
        elif raw_value <= 3:
            return ComplexityTier.L
        else:  # 4+
            return ComplexityTier.XL

    # Should never reach here
    raise ScoringValidationError(
        f"Unexpected attribute_id: {attribute_id}",
        context={"attribute_id": attribute_id},
    )


def exceeds_xl_ceiling(attribute_id: int, raw_value: int) -> bool:
    """Check if a value exceeds the XL ceiling for an attribute.

    XL ceilings define the maximum normal values for each attribute.
    Values exceeding the ceiling may require Tech Lead review.

    Args:
        attribute_id: Attribute ID (1-5)
        raw_value: The raw value to check

    Returns:
        True if raw_value exceeds the XL ceiling

    Raises:
        ScoringValidationError: If attribute_id is invalid
    """
    if attribute_id not in _ATTRIBUTE_NAMES:
        raise ScoringValidationError(
            f"Invalid attribute_id: {attribute_id}. Must be 1-5.",
            context={"attribute_id": attribute_id},
        )

    ceiling = _XL_CEILINGS.get(attribute_id, float("inf"))
    return raw_value > ceiling
