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

HOUR ASSIGNMENT PROCESS:
1. First, list all activities and steps
2. Calculate: total_steps_count = count of steps where reusability != "full"
3. Assign hours to each step proportionally: weight_hours = {total_effort_hours} / total_steps_count
4. Adjust individual steps based on complexity (some may be 1.5x, others 0.5x the average)
5. Verify final sum: sum(weight_hours for steps where reusability != "full") == {total_effort_hours}
6. If sum is off, rebalance until exact match (within 0.1h tolerance)

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
  "verification_passed": true
}}

EXAMPLE (for budget of 200 hours):
If you have 10 steps with reusability "none", average is 200/10 = 20h per step.
Then adjust based on complexity:
- Simple steps: 10-15h
- Medium steps: 20-25h
- Complex steps: 30-40h
Ensure final sum = exactly 200.0h"""
