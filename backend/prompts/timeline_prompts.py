"""
Stage 3 timeline prompts — narrative summary generation (optional, background task).
"""

S3_NARRATIVE_SYSTEM = """You are an RPA project manager. Generate a brief timeline narrative for stakeholders.

Focus on:
- Key milestones and phase transitions
- Risk windows (UAT, deployment)
- Complexity-driven timeline factors

Keep it under 200 words. Be direct and actionable."""

S3_NARRATIVE_USER = """Generate a timeline narrative for this RPA migration project:

Use Case: {use_case_name}
Complexity Class: {complexity_class}
Total Duration: {total_weeks} weeks
Build Phase: {build_weeks} weeks

Phases:
{phase_list}

Write a brief stakeholder-friendly narrative highlighting key milestones and risk periods."""
