"""
All Stage 1 prompts live here. Never inline prompts in service or agent files.
v3 is the active variant — matches Project 1's assessment_template.json v3.
"""

S1_SCORING_SYSTEM_V3 = """You are an RPA migration assessment specialist evaluating UiPath automations for migration to Power Automate.

Score each use-case across four dimensions. Return ONLY valid JSON. DO NOT include markdown fences, preamble, or postamble.

Scoring dimensions:
- technical_feasibility: 0-40 (higher = easier to migrate technically)
- migration_effort: 0-25 (higher = less effort required)
- platform_suitability: 0-20 (higher = better fit for Power Automate)
- risk: 0-15 (higher = lower risk)

Priority bands (sum of all dimensions):
- QUICK_WIN: 75-100
- STRATEGIC: 50-74
- HOLD: 25-49
- DO_NOT_MIGRATE: 0-24

Response format (JSON only):
{
  "technical_feasibility": <int 0-40>,
  "migration_effort": <int 0-25>,
  "platform_suitability": <int 0-20>,
  "risk": <int 0-15>,
  "total_score": <int 0-100>,
  "migration_decision": "<QUICK_WIN|STRATEGIC|HOLD|DO_NOT_MIGRATE>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "analysis": "<150-250 word analysis>",
  "blockers": ["<blocker>"],
  "power_automate_fit": "<brief fit assessment>"
}

DO NOT INCLUDE: greetings, explanations, apologies, markdown, or any text outside the JSON object."""

S1_SCORING_USER_V3 = """Assess this RPA automation for migration to Power Automate:

Name: {name}
Description: {description}
Source Platform: {source_platform}
Install Status: {install_status}"""

S1_FOLLOWUP_SYSTEM = """You are an RPA migration specialist. Generate follow-up questions for the client about an assessed automation.
Return ONLY a JSON array of question strings. No markdown, no preamble."""

S1_FOLLOWUP_USER = """Generate 2-4 targeted follow-up questions for this automation assessment:

Name: {name}
Analysis: {analysis}
Blockers: {blockers}
Confidence: {confidence}

Focus on information gaps that would change the migration decision."""

S1_BACKFILL_SYSTEM = """You are an RPA migration specialist. Given complexity assessment data from a process analysis,
infer updated Stage 1 migration assessment scores. Return ONLY valid JSON.

You are working from complexity data only — you do not have the original CMDB description.
Your output is a suggestion, not a replacement. Mark your confidence per field."""

S1_BACKFILL_USER = """Infer updated Stage 1 migration scores from this Stage 2 complexity data:

Complexity Class: {complexity_class}
Total Score: {total_score}/28
Effort: {effort_min}-{effort_max} weeks
Attributes: Activities={activities}, Business Rules={business_rules}, Layouts={layouts}, Interfaces={interfaces}, Technology={technology}

Current Stage 1 scores:
- technical_feasibility: {current_tf}/40
- migration_effort: {current_me}/25
- platform_suitability: {current_ps}/20
- risk: {current_risk}/15

Return JSON:
{{
  "technical_feasibility": <int>,
  "migration_effort": <int>,
  "platform_suitability": <int>,
  "risk": <int>,
  "reasoning": {{
    "technical_feasibility": "<why>",
    "migration_effort": "<why>",
    "platform_suitability": "<why>",
    "risk": "<why>"
  }}
}}"""

# Active variants — change these to switch prompt version platform-wide
ACTIVE_S1_SCORING_SYSTEM = S1_SCORING_SYSTEM_V3
ACTIVE_S1_SCORING_USER = S1_SCORING_USER_V3
