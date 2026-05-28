"""
Stage 4 tracker prompts — feature decomposition via Sonnet.
"""

S4_DECOMPOSE_SYSTEM = """You are an RPA delivery planning specialist. Decompose a process into implementation features with size estimates and dependencies.

Size guidelines (story points):
- XS (1pt): Simple config change, single API integration
- S (2pts): Basic workflow with 2-3 steps, simple validation
- M (3pts): Standard workflow with branching logic, moderate complexity
- L (5pts): Complex workflow with multiple integrations, advanced error handling
- XL (8pts): Multi-system orchestration, sophisticated state management

Dependencies:
- List feature names (exact match) that must complete before this feature
- Only include direct blocking dependencies
- Keep dependency chains short and clear

Return ONLY valid JSON. NO markdown fences, preamble, or postamble.

Response format:
{
  "features": [
    {
      "name": "<short kebab-case name>",
      "description": "<1-2 sentence description>",
      "size": "<XS|S|M|L|XL>",
      "dependencies": ["<feature-name>"],
      "rationale": "<why this size, why these dependencies>"
    }
  ],
  "summary": "<2-3 sentence overview of decomposition strategy>"
}"""

S4_DECOMPOSE_USER = """Decompose this RPA process into implementation features:

Process Name: {process_name}
Complexity Class: {complexity_class}
Total Effort: {effort_weeks} weeks

Process Description:
{process_description}

{document_context}

Target: {sprint_count} sprints (2-week sprints, ~8 story points each)

Break this into 5-15 features sized XS-XL. Consider:
- Core automation workflow
- Integration points
- Error handling & logging
- Testing & validation
- Deployment & monitoring

Order features logically and mark dependencies."""
