# Attribute Validation Tools

Tools for validating complexity band assignments against the weight matrix.

## Purpose

These tools expose the weight matrix logic as callable functions, enabling:

1. **Testing**: Verify band assignments are correct for given counts
2. **Debugging**: Understand why a specific band was assigned
3. **Documentation**: Reference for weight matrix rules
4. **Future Enhancement**: Can be exposed to LLM agents for self-validation

## Available Functions

### `get_band_for_count(attribute_name, count)`

Returns the correct band for a given attribute count.

```python
from tools.analysis.attribute_validation_tool import get_band_for_count

# Example: 3 business rules → L band
band = get_band_for_count("business_rules", 3)
assert band == "L"

# Example: 15 activities → M band
band = get_band_for_count("activities", 15)
assert band == "M"
```

**Mapping Logic (from weight_matrix.py)**:

- **Activities**: ≤10→S, 11-20→M, 21-40→L, 41+→XL
- **Business Rules**: 0→S, 1-2→M, 3-4→L, 5+→XL
- **Layouts**: 1→S, 2-3→M, 4-6→L, 7+→XL
- **Interfaces**: 0-2→S, 3-4→M, 5-6→L, 7+→XL
- **Technology**: 0→S, 1→M, 2-3→L, 4+→XL

### `get_attribute_definitions()`

Returns clear descriptions of what each attribute represents.

```python
from tools.analysis.attribute_validation_tool import get_attribute_definitions

defs = get_attribute_definitions()
print(defs["business_rules"])
# → "Number of conditional logic branches or decision rules..."
```

Use this to understand the distinction between similar attributes (e.g., layouts vs interfaces).

### `get_band_ranges()`

Returns the count ranges for each band across all attributes.

```python
from tools.analysis.attribute_validation_tool import get_band_ranges

ranges = get_band_ranges()
print(ranges["business_rules"]["L"])
# → "3-4 rules"
```

### `validate_band_assignment(attribute_name, count, assigned_band)`

Validates that a band assignment matches the expected band for the count.

```python
from tools.analysis.attribute_validation_tool import validate_band_assignment

# Correct assignment
result = validate_band_assignment("business_rules", 3, "L")
assert result["valid"] == True

# Incorrect assignment
result = validate_band_assignment("business_rules", 3, "S")
assert result["valid"] == False
assert result["expected_band"] == "L"
assert "should be L, not S" in result["message"]
```

## Usage Examples

### Verify Ground Truth Test Case

```python
from tools.analysis.attribute_validation_tool import get_band_for_count

# Ground truth from CLAUDE.md:
# Activities XL→8, Business Rules XL→8, Layouts L→3, Interfaces S→1, Technology S→1
# Total: 21 → Classification: L

bands = {
    "activities": get_band_for_count("activities", 50),     # → XL
    "business_rules": get_band_for_count("business_rules", 5),  # → XL
    "layouts": get_band_for_count("layouts", 5),            # → L
    "interfaces": get_band_for_count("interfaces", 1),      # → S
    "technology": get_band_for_count("technology", 1),      # → M
}

print(bands)
# Should match expected bands
```

### Debug Band Misclassification

```python
from tools.analysis.attribute_validation_tool import validate_band_assignment

# Scenario: LLM extracted 3 business rules but assigned band "S"
# Expected: band should be "L" for 3 rules

result = validate_band_assignment("business_rules", 3, "S")
print(result)
# {
#   "valid": False,
#   "expected_band": "L",
#   "message": "Count of 3 should be L, not S"
# }
```

### Batch Validation

```python
from tools.analysis.attribute_validation_tool import get_band_for_count

# Extracted from document
document_counts = {
    "activities": 12,
    "business_rules": 3,
    "layouts": 2,
    "interfaces": 1,
    "technology": 0,
}

# Get correct bands
correct_bands = {
    attr: get_band_for_count(attr, count)
    for attr, count in document_counts.items()
}

print(correct_bands)
# {
#   "activities": "M",      # 12 activities → M
#   "business_rules": "L",  # 3 rules → L
#   "layouts": "M",         # 2 layouts → M
#   "interfaces": "S",      # 1 interface → S
#   "technology": "S"       # 0 technology → S
# }
```

## Integration with QualityEvaluator

The `QualityEvaluator` in `core/quality.py` performs structural validation (checks for valid band values like "XS", "S", etc.). These tools provide **semantic validation** - ensuring the band matches the count.

## Future Enhancement: LLM Tool Binding

These functions are designed to be callable by LLM agents (via LangChain tool binding or function calling). If the process agent is upgraded to use tools, it could:

1. Count items in document (e.g., "I found 3 business rules")
2. Call `get_band_for_count("business_rules", 3)` → Returns "L"
3. Self-validate before returning final answer

**Note**: Current architecture uses prompt-based extraction with post-hoc validation. Tool binding would require architectural changes to the process agent StateGraph.

## Testing

Run the validation tool tests:

```bash
cd backend
uv run pytest tests/unit/test_attribute_validation_tool.py -v
```

## Related Files

- `core/scoring/weight_matrix.py` - Source of truth for band mapping logic
- `core/quality.py` - Structural validation (valid band values)
- `agents/process_agent.py` - Band extraction agent (could use these tools)
- `data/reference/weight_matrix.json` - Weight matrix data file
