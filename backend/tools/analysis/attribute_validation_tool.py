"""
Attribute validation tools for LLM agents.

Exposes weight matrix functions as LLM-callable tools so agents can:
1. Validate band assignments by checking counts against weight matrix rules
2. Understand attribute definitions to guide extraction
3. Get the correct band for a given count

These tools allow the process agent to self-validate during extraction,
reducing misclassification errors.
"""

from core.scoring.weight_matrix import (
    _ATTRIBUTE_IDS,
    load_full_weight_data,
    map_value_to_tier,
)


def get_band_for_count(attribute_name: str, count: int) -> str:
    """
    LLM-callable: Given attribute name and count, return appropriate band.

    This is the KEY function agents should use to validate their band assignments.
    Instead of guessing which band applies, the agent can count items and call
    this function to get the authoritative answer from the weight matrix.

    Args:
        attribute_name: One of "activities", "business_rules", "layouts",
                       "interfaces", or "technology"
        count: Number of items counted in the document

    Returns:
        Band string: "S", "M", "L", or "XL"

    Raises:
        KeyError: If attribute_name is not recognized
        ValueError: If count is negative

    Example:
        >>> get_band_for_count("business_rules", 3)
        "L"
        >>> get_band_for_count("activities", 15)
        "M"
    """
    if attribute_name not in _ATTRIBUTE_IDS:
        valid_attrs = ", ".join(_ATTRIBUTE_IDS.keys())
        raise KeyError(
            f"Unknown attribute '{attribute_name}'. Valid attributes: {valid_attrs}"
        )

    if count < 0:
        raise ValueError(f"Count must be non-negative, got {count}")

    attribute_id = _ATTRIBUTE_IDS[attribute_name]
    tier = map_value_to_tier(attribute_id, count)
    return tier.value


def get_attribute_definitions() -> dict[str, str]:
    """
    Return attribute definitions to help agents understand what to count.

    Provides clear descriptions of what each attribute represents, which helps
    agents distinguish between similar concepts (e.g., layouts vs interfaces).

    Returns:
        dict mapping attribute names to their definitions

    Example:
        >>> defs = get_attribute_definitions()
        >>> print(defs["business_rules"])
        "Number of conditional logic branches or decision rules..."
    """
    return {
        "activities": (
            "Activity is a piece of work that forms one logical step within a process. "
            "Each activity represents a distinct action or task the automation performs. "
            "Examples: 'Read email', 'Extract invoice data', 'Update database record'."
        ),
        "business_rules": (
            "Number of conditional logic branches or decision rules the automation must evaluate. "
            "Each 'if-then-else' condition, validation check, or approval workflow counts as one rule. "
            "Examples: 'If amount > 10000 then route to manager', 'If vendor not found then create new'."
        ),
        "layouts": (
            "Number of distinct UI screens, forms, or layouts the bot interacts with. "
            "Each unique screen design or window the bot must navigate counts as one layout. "
            "Examples: Login screen, main dashboard, invoice entry form, confirmation dialog."
        ),
        "interfaces": (
            "Number of external system integrations (APIs, databases, applications) the automation connects to. "
            "Each separate system or data source counts as one interface. "
            "Examples: SAP ERP system, Oracle database, Salesforce API, email server."
        ),
        "technology": (
            "Number of technology integration points required beyond the primary RPA tool. "
            "Each additional technical component or capability needed counts as one technology. "
            "Examples: OCR for document scanning, API connector, database driver, Excel automation."
        ),
    }


def get_band_ranges() -> dict[str, dict[str, str]]:
    """
    Return the count ranges for each band across all attributes.

    This helps agents understand the thresholds: "How many business rules
    puts me in the L band?" The answer is in the returned data.

    Returns:
        Nested dict: {attribute_name: {band: range_description}}

    Example:
        >>> ranges = get_band_ranges()
        >>> print(ranges["business_rules"]["L"])
        "3-4 rules"
    """
    full_data = load_full_weight_data()
    result: dict[str, dict[str, str]] = {}

    for attr_name, tiers in full_data.items():
        result[attr_name] = {}
        for tier_name, tier_info in tiers.items():
            result[attr_name][tier_name] = tier_info.get("range", "")

    return result


def validate_band_assignment(
    attribute_name: str, count: int, assigned_band: str
) -> dict[str, bool | str]:
    """
    Validate that a band assignment matches the count.

    Agents can use this to double-check their work before finalizing extraction.

    Args:
        attribute_name: Attribute being validated
        count: Number of items counted
        assigned_band: Band the agent assigned

    Returns:
        dict with keys:
            - valid: bool, True if assignment is correct
            - expected_band: str, what the band should be
            - message: str, explanation

    Example:
        >>> validate_band_assignment("business_rules", 3, "L")
        {"valid": True, "expected_band": "L", "message": "Correct assignment"}

        >>> validate_band_assignment("business_rules", 3, "S")
        {"valid": False, "expected_band": "L", "message": "Count of 3 should be L, not S"}
    """
    expected_band = get_band_for_count(attribute_name, count)
    is_valid = expected_band == assigned_band

    if is_valid:
        return {
            "valid": True,
            "expected_band": expected_band,
            "message": "Correct assignment",
        }
    else:
        return {
            "valid": False,
            "expected_band": expected_band,
            "message": f"Count of {count} should be {expected_band}, not {assigned_band}",
        }
