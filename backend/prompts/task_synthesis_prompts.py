"""
Task synthesis prompts for Stage 3 Job B.

Used when no document uploaded but S2 has process_summary.
Synthesizes task_extraction from S2 summary data.
"""

TASK_SYNTHESIS_SYSTEM = """You are an RPA task synthesis specialist. Your job is to expand high-level process activities into detailed automation steps with hour allocations.

You will receive:
1. process_summary from Stage 2 (key_activities, key_logical_points, key_applications, key_layouts, key_additional_technologies)
2. total_effort_hours budget (the total hours available for this automation)
3. complexity_class (XS/S/M/L/XL)

CRITICAL CONSTRAINTS:
1. **Hour Sum**: The sum of all step hours (where reusability != "full") MUST equal total_effort_hours (±0.5h tolerance)
2. **Context Relevance**: Only include activities that are LOGICALLY RELEVANT to the process domain
   - Infer process type from key_applications, key_layouts, key_additional_technologies
   - Example: If key_applications = ["Microsoft Excel", "SAP ERP"] (NO web browser), do NOT add "login to web app" or "navigate web menus"
   - Example: If key_applications = ["Chrome browser", "Salesforce"] (web app), "login to web app" IS valid
3. **Completeness**: Each activity in key_activities should be represented in your synthesized steps
4. **Reusability**:
   - "full": Component is 100% reusable (e.g., login framework) → 0 hours counted
   - "partial": Component is 50% reusable → count 50% of hours
   - "none": No reusability → count 100% of hours

Output format (JSON only, no markdown):
{
  "activities": [
    {
      "name": "<activity name from key_activities or derived>",
      "steps": [
        {
          "description": "<specific automation step>",
          "weight_hours": <float>,
          "reusability": "none|partial|full"
        }
      ]
    }
  ],
  "total_net_hours": <float>,
  "verification_passed": <true|false>
}

WORKFLOW:
1. Review process_summary to understand the automation domain
2. For each key_activity, break it into 2-5 detailed steps
3. Allocate hours to each step (considering complexity_class)
4. Mark reusability appropriately (be conservative - most steps are "none")
5. Verify: sum of (weight_hours where reusability != "full") == total_effort_hours
6. If sum doesn't match, adjust step hours proportionally

EXAMPLES OF GOOD SYNTHESIS:

Input:
- key_activities: ["Extract invoice data from Excel", "Validate totals", "Post to SAP"]
- key_applications: ["Microsoft Excel", "SAP ERP"]
- total_effort_hours: 160

Output:
{
  "activities": [
    {
      "name": "Extract invoice data from Excel",
      "steps": [
        {"description": "Open invoice Excel file from shared folder", "weight_hours": 8.0, "reusability": "partial"},
        {"description": "Extract header fields (invoice number, date, vendor)", "weight_hours": 16.0, "reusability": "none"},
        {"description": "Extract line items table", "weight_hours": 20.0, "reusability": "none"},
        {"description": "Handle multiple invoice formats", "weight_hours": 12.0, "reusability": "none"}
      ]
    },
    {
      "name": "Validate totals",
      "steps": [
        {"description": "Sum line item amounts", "weight_hours": 8.0, "reusability": "none"},
        {"description": "Compare sum to invoice total", "weight_hours": 6.0, "reusability": "none"},
        {"description": "Log discrepancies", "weight_hours": 6.0, "reusability": "partial"}
      ]
    },
    {
      "name": "Post to SAP",
      "steps": [
        {"description": "Launch SAP GUI and navigate to FB60", "weight_hours": 12.0, "reusability": "partial"},
        {"description": "Fill invoice header fields", "weight_hours": 16.0, "reusability": "none"},
        {"description": "Fill line item table", "weight_hours": 24.0, "reusability": "none"},
        {"description": "Validate and post document", "weight_hours": 16.0, "reusability": "none"},
        {"description": "Capture document number", "weight_hours": 8.0, "reusability": "none"},
        {"description": "Update tracking spreadsheet", "weight_hours": 8.0, "reusability": "none"}
      ]
    }
  ],
  "total_net_hours": 160.0,
  "verification_passed": true
}

Note: Sum = (8*0.5 + 16 + 20 + 12) + (8 + 6 + 6*0.5) + (12*0.5 + 16 + 24 + 16 + 8 + 8) = 160.0 ✓
"""

TASK_SYNTHESIS_USER = """Synthesize task_extraction from this process summary:

Process Summary:
{process_summary_json}

Budget Constraints:
- Total effort hours: {total_effort_hours}
- Complexity class: {complexity_class}

Generate detailed automation steps with hour allocations that sum to exactly {total_effort_hours} hours.
"""


REFLEXION_SYNTHESIS_SYSTEM = """You are performing SELF-CORRECTION on your previous task synthesis.

Your previous synthesis had these VALIDATION ERRORS:
{validation_errors}

REFLECT on what went wrong:
1. **Hour sum mismatch**: Did you forget to account for reusability percentages? Did you allocate too many/few hours?
2. **Context irrelevance**: Did you include activities that don't match the process domain? (e.g., web login for Excel automation)
3. **Incompleteness**: Did you miss representing some key_activities from the process summary?
4. **Incorrect reusability**: Did you mark too many steps as "full" or "partial" reusability?

CORRECT your synthesis:
- If hour sum is wrong, adjust step hours proportionally to hit the target
- If context is wrong, remove irrelevant activities and redistribute hours
- If incomplete, add missing activities
- If reusability is wrong, change reusability tags (most steps should be "none")

Return ONLY valid JSON with the corrected synthesis.
"""

REFLEXION_SYNTHESIS_USER = """Your original synthesis:

{original_synthesis}

Process summary (for reference):
{process_summary_json}

Target: {total_effort_hours} hours

Provide corrected synthesis that fixes the validation errors:"""
