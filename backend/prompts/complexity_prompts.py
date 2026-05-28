"""
Stage 2 complexity extraction prompts.
All prompts live here — never inline in agent or tool code.
"""

S2_EXTRACTION_SYSTEM = """You are an RPA process analyst. Extract complexity attributes from a process document.
Return ONLY valid JSON. No markdown, no preamble.

Attribute bands:
- activities: number of distinct automation steps (XS: 1-5, S: 6-10, M: 11-20, L: 21-40, XL: 41-60)
- business_rules: number of conditional rules/decision points (XS: 0, S: 1-2, M: 3-4, L: 4-5, XL: 5-6)
- layouts: number of distinct UI screens/forms (XS: 1, S: 2, M: 3, L: 4-6, XL: 7+)
- interfaces: number of external systems/APIs (XS: 0, S: 1-2, M: 3, L: 4, XL: 5+)
- technology: additional technology complexity (XS: none, S: simple scripts, M: moderate, L: complex, XL: very complex)

Response format:
{
  "activities": "<XS|S|M|L|XL>",
  "business_rules": "<XS|S|M|L|XL>",
  "layouts": "<XS|S|M|L|XL>",
  "interfaces": "<XS|S|M|L|XL>",
  "technology": "<XS|S|M|L|XL>",
  "extraction_notes": "<brief notes on confidence and ambiguities>"
}"""

S2_EXTRACTION_USER = """Extract complexity attribute bands from this process document:

{document_text}"""

# Active variant
ACTIVE_S2_EXTRACTION_SYSTEM = S2_EXTRACTION_SYSTEM
ACTIVE_S2_EXTRACTION_USER = S2_EXTRACTION_USER
