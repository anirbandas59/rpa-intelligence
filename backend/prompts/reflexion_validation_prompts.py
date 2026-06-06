"""
Reflexion validation prompts for S2 process_summary self-correction.

Used when process_summary arrays don't align with assigned complexity bands.
"""

REFLEXION_S2_JUSTIFICATION_SYSTEM = """You are an RPA process analyst performing self-validation.

You previously classified a process with these complexity bands:
- activities: {activities_band}
- business_rules: {business_rules_band}
- layouts: {layouts_band}
- interfaces: {interfaces_band}
- technology: {technology_band}

However, your process_summary arrays do NOT justify these classifications:

VALIDATION ERRORS:
{validation_errors}

Expected array counts based on bands:
- activities={activities_band} expects {activities_range} items in key_activities (you provided {activities_count})
- business_rules={business_rules_band} expects {business_rules_range} items in key_logical_points (you provided {business_rules_count})
- layouts={layouts_band} expects {layouts_range} items in key_layouts (you provided {layouts_count})
- interfaces={interfaces_band} expects {interfaces_range} items in key_applications (you provided {interfaces_count})
- technology={technology_band} expects {technology_range} items in key_additional_technologies (you provided {technology_count})

REFLECT on why this mismatch occurred:
1. Did you misclassify the band? (e.g., you said activities=M but it's actually XS)
2. Did you fail to list all relevant items in the array?
3. Did you include irrelevant items that shouldn't count?

CORRECT your extraction by choosing ONE:
A. Adjust the band classification to match the array count
B. Expand/reduce the array to match the band classification

Return ONLY valid JSON with corrected bands AND process_summary.
"""

REFLEXION_S2_JUSTIFICATION_USER = """Your original extraction:

{original_extraction}

Provide corrected extraction with aligned bands and process_summary arrays:"""


# Band count ranges for validation
BAND_RANGES = {
    "activities": {
        "XS": "1-5",
        "S": "6-10",
        "M": "11-20",
        "L": "21-40",
        "XL": "41+",
    },
    "business_rules": {
        "XS": "0",
        "S": "1-2",
        "M": "3-4",
        "L": "4-5",
        "XL": "5-6",
    },
    "layouts": {
        "XS": "1",
        "S": "2",
        "M": "3",
        "L": "4-6",
        "XL": "7+",
    },
    "interfaces": {
        "XS": "0",
        "S": "1-2",
        "M": "3",
        "L": "4",
        "XL": "5+",
    },
    "technology": {
        "XS": "0",
        "S": "1-2",
        "M": "3-4",
        "L": "5-6",
        "XL": "7+",
    },
}
