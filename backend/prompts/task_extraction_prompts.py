"""Stage 3 Job A prompts — task extraction with hour-sum constraint."""

# SYSTEM prompt is a template — {total_effort_hours} substituted at call time
TASK_EXTRACTION_SYSTEM = """You are an RPA process analyst. You will receive a process document (PDD or SDD), process context from Stage 2 complexity analysis, and a total effort budget in hours. Your task is to extract the complete work breakdown of the process into activities and steps.

CRITICAL CONSTRAINT: The sum of all step weights WHERE reusability is NOT "full" must equal exactly {total_effort_hours} hours. This is a hard constraint. Calibrate the granularity of your decomposition to fit this budget.

CONTEXT USAGE:
- Use the Stage 2 process summary as your primary understanding of the process
- The key activities, business rules, applications, and technologies identified in Stage 2 should guide your task breakdown
- You MAY add logical activities not explicitly mentioned (e.g., login/logout for SAP/web apps) if they support the identified technologies
- Your task breakdown must align with the Stage 2 process understanding

Reusability levels:
- "full": Component already built, 0 additional effort (DO NOT include in hour sum)
- "partial": Shared logic exists, reduced effort (50% of typical - INCLUDE in hour sum)
- "none": Net-new build required (full effort - INCLUDE in hour sum)

Return ONLY valid JSON. No preamble, no explanation, no markdown fences."""

# USER prompt is a template — all {placeholders} substituted at call time
TASK_EXTRACTION_USER = """Process document:
{document_text}
{process_context}

Total effort budget: {total_effort_hours} hours
Hour tolerance: {hour_tolerance}h (±{hour_tolerance_percentage}%)
Process name: {process_name}

TASK:
Extract activities and steps that align with the Stage 2 process understanding shown above. For each step, you MUST assign:
- description: what the developer must build
- weight_hours: estimated build hours (MUST be a positive number > 0 for steps with reusability != "full")
- reusability: "full" | "partial" | "none"

CRITICAL: Every step with reusability "none" or "partial" MUST have weight_hours > 0. DO NOT assign 0.0 hours to development steps!

ALIGNMENT RULES:
- Your activities should directly relate to the key activities identified in Stage 2
- Break down each key activity into implementable development steps
- You may add logical support activities (login, error handling, logging) if they relate to the identified applications/technologies
- Do NOT invent entirely new business processes not mentioned in the Stage 2 context

HOUR ASSIGNMENT PROCESS (MANDATORY):
1. First, list all activities and steps
2. Calculate: total_steps_count = count of steps where reusability != "full"
3. Assign hours proportionally: base_hours = {total_effort_hours} / total_steps_count
4. Adjust individual steps based on complexity:
   - Simple steps: 0.5x base_hours
   - Medium steps: 1.0x base_hours
   - Complex steps: 1.5-2.0x base_hours
5. **REASONABLENESS CHECK**: For each step, ask: "Can a developer complete this in the allocated hours?"
   - Hours must be REALISTIC — not too short to be rushed, not too inflated to be rejected
   - If a step seems under-budgeted, increase it; if over-budgeted, reduce it
6. **CALCULATE THE SUM MANUALLY** (CRITICAL):
   - Go through each step and calculate: net_hours = weight_hours (if reusability="none") OR weight_hours × 0.5 (if reusability="partial") OR 0 (if reusability="full")
   - Add up all net_hours: total_sum = sum of all net_hours
7. **VERIFY AGAINST TARGET**:
   - Tolerance: Acceptable range is {hour_tolerance_min}h to {hour_tolerance_max}h
   - Check: Is total_sum within this range?
   - If NO: Adjust step hours proportionally until total_sum falls within range
   - If YES: Proceed to output
8. **SET FIELDS CORRECTLY**:
   - Set total_net_hours = your actual calculated total_sum (not the target value!)
   - Set verification_passed = true if within tolerance, false otherwise
   - DO NOT lie about the sum - set it to your actual calculation

VERIFICATION:
Include these fields in your JSON response:
{{
  "total_net_hours": <sum of hours where reusability != "full">,
  "verification_passed": <true if sum within tolerance range>,
  "verification_notes": "<explain any adjustments made>"
}}

CONTEXT ALIGNMENT RULES (MANDATORY):
- Your activities MUST directly relate to the key_activities in Stage 2 process summary
- Do NOT invent business processes not mentioned in process_summary
- You MAY add technical support activities (login, error handling, logging) IF:
  * They relate to identified key_applications or key_additional_technologies
  * Example: If key_applications includes "SAP ERP", login to SAP is valid
  * Example: If key_applications is ["Microsoft Excel"], do NOT add web login
- Activities must be LOGICALLY RELEVANT to the process domain

Required JSON structure:
{{
  "activities": [
    {{
      "name": "activity name",
      "steps": [
        {{
          "description": "step description",
          "weight_hours": 15.0,
          "reusability": "none"
        }},
        {{
          "description": "another step",
          "weight_hours": 12.5,
          "reusability": "partial"
        }}
      ]
    }}
  ],
  "total_net_hours": 27.5,
  "verification_passed": true,
  "verification_notes": "Adjusted hours to ensure realistic developer estimates"
}}

EXAMPLE WITH STEP-BY-STEP VERIFICATION:

Target: 160h, tolerance: ±48h, acceptable range: 112-208h

Initial allocation (10 steps, all "none"):
- Step 1: 15h → net: 15h × 1.0 = 15.0h
- Step 2: 20h → net: 20h × 1.0 = 20.0h
- Step 3: 18h → net: 18h × 1.0 = 18.0h
- Step 4: 12h → net: 12h × 1.0 = 12.0h
- Step 5: 25h → net: 25h × 1.0 = 25.0h
- Step 6: 16h → net: 16h × 1.0 = 16.0h
- Step 7: 14h → net: 14h × 1.0 = 14.0h
- Step 8: 22h → net: 22h × 1.0 = 22.0h
- Step 9: 10h → net: 10h × 1.0 = 10.0h
- Step 10: 8h → net: 8h × 1.0 = 8.0h

CALCULATE SUM: 15 + 20 + 18 + 12 + 25 + 16 + 14 + 22 + 10 + 8 = 160.0h

CHECK: Is 160.0h within 112-208h range? YES ✓

Result:
{{
  "total_net_hours": 160.0,
  "verification_passed": true
}}

EXAMPLE WITH MIXED REUSABILITY:

Target: 200h, tolerance: ±60h, range: 140-260h

Steps with mixed reusability:
- Step A: 16h, reusability="none" → net: 16.0h
- Step B: 20h, reusability="partial" → net: 20.0 × 0.5 = 10.0h
- Step C: 24h, reusability="none" → net: 24.0h
- Step D: 12h, reusability="full" → net: 0.0h (not counted!)
- Step E: 30h, reusability="none" → net: 30.0h
... (continue for all steps)

CALCULATE SUM: 16.0 + 10.0 + 24.0 + 0.0 + 30.0 + ... = X hours

CHECK: Is X within 140-260h? Adjust if needed.

Set total_net_hours = X (your actual sum, not 200!)"""
