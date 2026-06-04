# Phase 4: LangGraph Complexity Agent Migration

## Overview

Phase 4 implements a **dual agent architecture** for Stage 2 complexity assessment, allowing safe migration from the v1 (legacy) simple pipeline to the v2 (LangGraph StateGraph) agent without breaking production.

## Feature Flag

```python
# backend/.env
USE_LANGGRAPH_COMPLEXITY_AGENT=false  # v1 legacy (default — safe)
USE_LANGGRAPH_COMPLEXITY_AGENT=true   # v2 LangGraph (new)
```

## Architecture

### V1 (Legacy) — Simple Pipeline

```
AttributeBands → score_attributes() → calculate_total() → classify() → lookup_effort() → ScoringResult
```

- **Agent**: `backend/agents/complexity_agent.py`
- **Tools**: `tools/attribute_scorer.py`, `tools/weighted_calculator.py`, `tools/classifier_tool.py`, `tools/effort_table_tool.py`
- **Returns**: `ScoringResult` (simple dict with total_score, complexity_class, effort_weeks, attribute_weights)
- **Characteristics**:
  - ✅ Simple, deterministic, fast
  - ✅ Zero LLM calls (pure Python math)
  - ✅ Proven in production
  - ❌ No state management
  - ❌ No LLM reasoning narratives
  - ❌ Not composable with other agents

### V2 (LangGraph) — StateGraph Agent

```
ComplexityAssessmentState (TypedDict)
  ↓
[score_attributes node] → raw_attributes → AttributeScore list
  ↓
[classify_complexity node] → deterministic classification + LLM reasoning
  ↓
AssessmentResult (richer output with confidence, reasoning, tech_lead_review)
```

- **Agent**: `backend/agents/complexity_assessment/agent.py`
- **Tools**: `tools/scoring/attribute_scorer.py`, `tools/scoring/classifier_tool.py`
- **Returns**: `AssessmentResult` (Pydantic model with confidence_score, reasoning, requires_tech_lead_review)
- **Characteristics**:
  - ✅ State-managed (ComplexityAssessmentState TypedDict)
  - ✅ Composable nodes (can add retry logic, conditional edges)
  - ✅ LLM reasoning narratives (Sonnet 4.5)
  - ✅ Confidence scoring (0.0-1.0 based on distance from tier boundaries)
  - ✅ Tech Lead review flagging (XL tier, score >25, ceiling violations)
  - ✅ Structured error handling (status, warnings, errors in state)
  - ✅ Consistent with project's other agents (tracker_agent, process_agent, project_orchestrator)
  - ⚠️ More complex (278 vs 69 lines)
  - ⚠️ LLM calls add latency (~3-8 seconds for reasoning)

## Adapter Layer

The orchestrator includes an adapter to maintain API compatibility:

```python
def assessment_to_scoring_result(assessment: AssessmentResult) -> ScoringResult:
    """Convert v2 AssessmentResult to v1 ScoringResult format."""
```

This ensures the API routes continue to work regardless of which agent is active.

## Testing

### Run v1 (legacy) tests:
```bash
uv run pytest tests/unit/test_s2_scoring.py -v
# 7 tests for v1 pipeline
```

### Run v2 (LangGraph) tests:
```bash
uv run pytest tests/unit/test_s2_langgraph.py -v
# 8 tests for v2 LangGraph agent
```

### Run ground truth tests:
```bash
uv run pytest tests/unit/test_ground_truth_scoring.py -v
# 8 tests verifying deterministic scoring (both v1 and v2 use same engine)
```

### Run all S2 tests:
```bash
uv run pytest tests/unit/test_s2_*.py tests/unit/test_ground_truth_scoring.py -v
# 23 total tests
```

## Validation Checklist

Before flipping the feature flag to `true`:

- [ ] All 23 S2 tests pass
- [ ] Ground truth test passes (Activities XL, Business Rules XL, Layouts L, Interfaces S, Technology S → L tier, total 21)
- [ ] v1 vs v2 equivalence test passes (same inputs → same deterministic scoring)
- [ ] API integration test passes (POST /api/v1/use-cases/{id}/s2/runs)
- [ ] Performance benchmark: v2 latency < v1 + 10 seconds
- [ ] Monitor logs for LangGraph errors

## Migration Steps

### Step 1: Validation Period (Current State)

```bash
USE_LANGGRAPH_COMPLEXITY_AGENT=false  # v1 active (default)
```

- ✅ v1 agent handles all S2 runs
- ✅ v2 agent tested in isolation via unit tests
- ✅ No production risk

### Step 2: Canary Testing (Optional)

```python
# Temporarily hardcode v2 for specific test use-cases
if use_case_id in ["test-uc-1", "test-uc-2"]:
    use_langgraph = True
```

- Run v2 agent for small subset of users
- Compare outputs manually
- Monitor latency, errors

### Step 3: Feature Flag Flip (Cutover)

```bash
USE_LANGGRAPH_COMPLEXITY_AGENT=true  # v2 active
```

- ✅ All S2 runs use v2 LangGraph agent
- ✅ API routes unchanged (adapter handles conversion)
- ✅ Frontend unchanged (ScoringResult format preserved)
- ⚠️ Monitor for:
  - Increased latency (LLM reasoning adds ~3-8s)
  - LLM provider errors (Anthropic rate limits)
  - State serialization errors (enum → string → enum)

### Step 4: Rollback Plan

If issues arise:

```bash
USE_LANGGRAPH_COMPLEXITY_AGENT=false  # revert to v1
```

- Instant rollback (no code changes needed)
- v1 agent immediately active
- Zero downtime

### Step 5: Deprecation (Future)

After 2 weeks of stable v2 production:

```bash
# Rename legacy agent
mv agents/complexity_agent.py agents/complexity_agent_legacy.py

# Add deprecation warning
@deprecated("Use complexity_assessment LangGraph agent instead")
def run_complexity_scoring(bands: AttributeBands) -> ScoringResult:
    ...
```

After 4 weeks with zero v1 usage:

```bash
# Remove v1 agent entirely
rm agents/complexity_agent_legacy.py
rm tools/attribute_scorer.py  # old version, replaced by tools/scoring/attribute_scorer.py
rm tools/weighted_calculator.py
rm tools/classifier_tool.py  # old version, replaced by tools/scoring/classifier_tool.py
rm tools/effort_table_tool.py
```

## Key Differences

| Aspect | v1 (Legacy) | v2 (LangGraph) |
|--------|-------------|----------------|
| **Total Score** | ✅ Same (deterministic) | ✅ Same (deterministic) |
| **Complexity Tier** | ✅ Same (S/M/L/XL) | ✅ Same (S/M/L/XL) |
| **Confidence Score** | ❌ Not available | ✅ 0.0-1.0 (distance from boundaries) |
| **Reasoning Narrative** | ❌ Not available | ✅ LLM-generated explanation |
| **Tech Lead Review** | ❌ Not flagged | ✅ Auto-flagged (XL tier, score >25) |
| **State Management** | ❌ No state | ✅ ComplexityAssessmentState (TypedDict) |
| **Error Recovery** | ❌ Fail fast | ✅ Status tracking (running/success/failed) |
| **Latency** | ⚡ Fast (~0.01s) | ⏱️ Moderate (~3-8s with LLM) |
| **LLM Calls** | 0 | 1 (reasoning generation) |

## Output Format

### v1 ScoringResult:
```json
{
  "total_score": 21,
  "complexity_class": "L",
  "effort_min_weeks": 6,
  "effort_max_weeks": 6,
  "attribute_weights": {
    "activities": 8,
    "business_rules": 8,
    "layouts": 3,
    "interfaces": 1,
    "additional_technology": 1
  }
}
```

### v2 AssessmentResult (full):
```json
{
  "session_id": "s2_run_abc123",
  "project_name": "Invoice Automation",
  "rpa_tool": "UIPATH",
  "attribute_scores": [
    {
      "attribute_id": 1,
      "attribute_name": "Activities",
      "attribute_desc": "Number of distinct activities/steps in the process",
      "raw_value": 45,
      "selected_tier": "XL",
      "weight": 8,
      "tier_rationale": "45 activities (41-60 activities) → Extra Large (XL) complexity tier"
    },
    ...
  ],
  "total_score": 21,
  "complexity_tier": "L",
  "confidence_score": 0.33,
  "reasoning": "This process has been assessed as Large (L) complexity with a score of 21/28. The primary complexity drivers are the high number of activities (45 steps) and business rules (5 decision points), both reaching XL tier. However, the moderate interface count and minimal technology requirements keep the overall classification at L tier. Consider decomposing the 45 activities into smaller, more manageable sub-processes to reduce migration effort.",
  "requires_tech_lead_review": false,
  "created_at": "2026-06-04T13:30:00Z"
}
```

### v2 AssessmentResult → v1 ScoringResult (adapter):
```json
{
  "total_score": 21,
  "complexity_class": "L",
  "effort_min_weeks": 6,
  "effort_max_weeks": 6,
  "attribute_weights": {
    "activities": 8,
    "business_rules": 8,
    "layouts": 3,
    "interfaces": 1,
    "additional_technology": 1
  }
}
```

## Monitoring

### Logs to Watch:

```bash
# V1 agent logs
grep "\[V1\] Running legacy complexity_agent" logs/rpa_agent.log

# V2 agent logs
grep "\[V2\] Running LangGraph complexity_assessment agent" logs/rpa_agent.log

# LLM reasoning generation
grep "Reasoning generated" logs/rpa_agent.log

# Errors
grep "Classification failed" logs/rpa_agent.log
grep "LangGraph agent failed" logs/rpa_agent.log
```

### Metrics to Track:

- **Latency**: v1 ~0.01s, v2 ~3-8s (expected)
- **Error Rate**: Target <1%
- **LLM Failures**: Graceful fallback (hardcoded reasoning)
- **Confidence Score Distribution**: Expect 0.2-0.8 average

## FAQ

### Q: Will the frontend need changes?
**A:** No. The adapter ensures ScoringResult format is preserved. Frontend sees no difference.

### Q: Can I A/B test v1 vs v2?
**A:** Yes, modify orchestrator to randomly assign:
```python
use_langgraph = random.random() < 0.5  # 50/50 split
```

### Q: What if LLM reasoning fails?
**A:** Hardcoded fallback is used:
```
"This process has been assessed as {tier} complexity with a score of {total_score}/28. Manual review recommended."
```

### Q: Does v2 change the scoring logic?
**A:** No. Both v1 and v2 use the **same deterministic weight matrix** from Phase 1. The `test_v1_v2_equivalence` test verifies this.

### Q: Why is v2 slower?
**A:** LLM reasoning generation adds ~3-8 seconds. This is optional and can be moved to a background task in the future.

### Q: When should I flip the flag?
**A:** When:
- All 23 tests pass
- Performance is acceptable
- LLM reasoning adds business value

## Next Steps (Post Phase 4)

### Phase 5 (Optional Enhancements):

1. **Make LLM reasoning async** (background task, non-blocking)
2. **Add conditional routing** (if confidence < 0.5, route to human review)
3. **Add parallel attribute scoring** (5x faster)
4. **Port Document Intelligence Agent** (automated PDF/DOCX extraction)
5. **Port Process Analysis Agent** (automated attribute extraction)
6. **Add checkpointing** (Redis session store for recovery)

## Conclusion

Phase 4 is **complete and production-ready**:

- ✅ Dual agent paths implemented
- ✅ Feature flag controls cutover
- ✅ All 23 tests pass
- ✅ API compatibility preserved
- ✅ Rollback plan in place
- ✅ v1 remains default (safe)

**Status**: Ready for canary testing and gradual rollout.
