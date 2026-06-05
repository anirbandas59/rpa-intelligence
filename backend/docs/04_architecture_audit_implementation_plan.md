# Architecture Audit & Implementation Plan

## Purpose

This document is the implementation guide for the next Claude Code session.
It audits the existing codebase against the corrected architecture and produces
a targeted, phase-ordered list of what to implement, extend, or fix.

It replaces a ground-up build plan. The system is substantially built.
The work is integration, correction, and the three net-new capabilities.

---

## Existing Codebase — What Is Already Built

### Backend (confirmed from file tree)

**Agents:**
- `agents/document_agent.py` — document text extraction
- `agents/process_agent.py` — process attribute identification
- `agents/complexity_agent.py` — complexity assessment (band scoring)
- `agents/orchestrator.py` — Stage 2 LangGraph orchestrator
- `agents/project_orchestrator.py` — project-level orchestrator
- `agents/tracker_agent.py` — Stage 4 tracker (needs audit against corrected spec)
- `agents/complexity_assessment/agent.py` — agent subpackage with prompts

**API routes (all four stages):**
- `api/v1/stage1.py` through `api/v1/stage4.py` — all present
- `api/v1/projects.py`, `api/v1/use_cases.py`, `api/v1/auth.py`
- `api/v1/settings.py`, `api/v1/orchestrator.py`, `api/v1/memory.py`
- `api/middleware/` — auth, error_handler, request_id
- `api/redis/redis_store.py` — job state store
- `api/sse_utils.py` — Server-Sent Events streaming

**Core:**
- `core/scoring/` — weight_matrix, classifier, effort_table (deterministic, unchanged)
- `core/models/` — assessment, document, process, scoring, timeline
- `core/exceptions.py`, `core/constants.py`, `core/quality.py`

**Tools:**
- `tools/` root level: attribute_scorer, classifier_tool, effort_table_tool,
  weighted_calculator, sprint_assigner
- `tools/scoring/` subdir: duplicate/reorganised versions of scoring tools
- `tools/registry.py`, `tools/registrations.py`, `tools/schemas.py`
  → Tool registry pattern already implemented

**Services:**
- `services/assessment_service.py` — Stage 1 wrapper
- `services/timeline_service.py` — Stage 3 phase calculator
- `services/export_service.py` — xlsx generation

**LLM:**
- `llm/manager.py` + providers: anthropic, openai, ollama, watsonx
  → Multi-provider already implemented beyond the plan's scope

**Memory:**
- `memory/episodic_memory.py` — cross-session memory
- `memory/session_memory.py` — within-session state

**Prompts:**
- `prompts/assessment_prompts.py` — Stage 1
- `prompts/complexity_prompts.py` — Stage 2
- `prompts/timeline_prompts.py` — Stage 3 (narrative only — Job A prompts missing)
- `prompts/tracker_prompts.py` — Stage 4 (needs hour-sum constraint audit)
- `prompts/orchestrator_prompts.py` — orchestrator

**DB:**
- `db/models.py`, `db/session.py`
- 6 migrations already applied (initial schema through agent sessions)

**Data:**
- `data/reference/weight_matrix.json`, `effort_table.json` — present
- `data/reference/rpa_tool_factors.json` — additional reference data
- `data/templates/` — empty (output_template.xlsx missing — CRITICAL GAP)
- `sp_conversion.json` — MISSING

### Frontend (confirmed from file tree)

**All four stage pages exist:**
- `app/(app)/projects/[id]/stage1-4/[ucId]/page.tsx`

**Shared components already built:**
- `AgentActivityFeed.tsx` — live agent activity display
- `AsyncRunProgress.tsx` — polling/progress for async runs
- `AutonomousRunButton.tsx` — trigger runs with streaming feedback
- `RunHistoryDrawer.tsx` — run history slide-in
- `StalenessIndicator.tsx` — stale result indicator
- `InputSourceBadge.tsx` — ai/manual/from_sN/corrected badges

**Streaming infrastructure:**
- `lib/hooks/useAgentStream.ts` — SSE streaming hook for agent activity

---

## Gap Analysis — What Is Missing or Needs Correction

### GAP 1 — `output_template.xlsx` is missing (CRITICAL)
**Location:** `data/templates/` directory exists but is empty.
**Impact:** `export_service.py` cannot function. Stage 4 export is broken.
**Fix:** Add the production tracker template (see Template Contract section below).

### GAP 2 — `sp_conversion.json` is missing
**Location:** `data/reference/`
**Impact:** SP conversion constant has no authoritative source.
**Fix:** Create the file (see content below).

### GAP 3 — `task_extraction_agent.py` does not exist
**Location:** Should be `agents/task_extraction_agent.py`
**Impact:** Stage 3 Job A (Sonnet step extraction from PDD) is not implemented.
  The two-job Stage 3 pattern cannot work without this agent.
**Fix:** Build new LangGraph StateGraph agent (see spec below).

### GAP 4 — `task_extraction_prompts.py` does not exist
**Location:** Should be `prompts/task_extraction_prompts.py`
**Impact:** Stage 3 Job A has no prompt. `timeline_prompts.py` is for narrative only.
**Fix:** Build new prompt file with hour-sum constraint (see spec below).

### GAP 5 — `tracker_sequencer.py` does not exist
**Location:** Should be `tools/output/tracker_sequencer.py`
  (or `tools/sprint_assigner.py` which exists but is sprint-based, not date-based)
**Impact:** Stage 4 cannot assign sequential calendar dates within Build+SIT window.
**Fix:** Build deterministic date sequencer (see spec below).

### GAP 6 — `tools/` directory structure is inconsistent
**Current state:** Scoring tools exist BOTH at `tools/` root AND in `tools/scoring/` subdir.
  `tools/analysis/` and `tools/output/` subdirs do not exist.
**Fix:** Consolidate. Move root-level duplicates into `tools/scoring/`. Create
  `tools/analysis/` and `tools/output/` subdirs. Update all imports.

### GAP 7 — Stage 3 two-job pattern needs verification
**File:** `api/v1/stage3.py` and `services/timeline_service.py`
**Required behaviour:** `POST /s3/runs` must:
  1. Run Job B (phase calculator) synchronously — return timeline immediately
  2. Queue Job A (task extraction) as background task — update record when complete
  3. `GET /readiness` must expose `s3_task_extraction: pending|complete|skipped`
**Fix:** Audit `stage3.py` and `timeline_service.py`. Add Job A background dispatch
  if not already present.

### GAP 8 — `tracker_prompts.py` needs hour-sum constraint audit
**File:** `prompts/tracker_prompts.py`
**Required:** Prompt must pass `total_effort_hours` as a hard constraint and instruct
  Sonnet to verify `Σ(tracker_row.hours) == total_effort_hours` before responding.
  If not present, add it.
**Fix:** Audit and update prompt.

### GAP 9 — `export_service.py` formula contract needs verification
**File:** `services/export_service.py`
**Required:** SP column must be written as formula string `=ROUND($C$16*Hours,2)`,
  never as a Python-computed float. Dev status column must be VLOOKUP formula.
  Dashboard rows 8–16 must never be written by Python.
**Fix:** Audit export_service.py against the xlsx template contract.

### GAP 10 — `tracker_agent.py` needs audit against corrected spec
**File:** `agents/tracker_agent.py`
**Required:** Stage 4 agent must NOT re-read the process document. It must receive
  `task_extraction` from Stage 3 as its input, group steps into WBS rows, and
  verify the hour sum matches the budget before returning.
**Current concern:** Agent may still be doing document decomposition (old spec).
**Fix:** Audit and correct if needed.

### GAP 11 — `core/assessment/` directory is empty
**Location:** `core/assessment/`
**Fix:** Either populate or remove. If Stage 1 assessment logic belongs here, move
  it from `services/assessment_service.py`. If not needed, delete to avoid confusion.

---

## Non-Negotiable StateGraph Architecture

Every AI-powered agent must be implemented as a LangGraph StateGraph.
No agent may make direct LLM calls outside of a StateGraph node.
This applies to all four stages and both new agents.

### Required StateGraph pattern (from Project 2, apply everywhere):

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from core.exceptions import AgentExecutionError
import logging

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    session_id: str          # threaded through ALL log lines
    use_case_id: str
    inputs: dict
    result: dict | None
    error: str | None

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("validate_inputs", validate_inputs)
    graph.add_node("run_llm", run_llm)
    graph.add_node("validate_output", validate_output)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("validate_inputs")
    graph.add_edge("validate_inputs", "run_llm")
    graph.add_conditional_edges(
        "run_llm",
        lambda s: "validate_output" if not s["error"] else "handle_error"
    )
    graph.add_edge("validate_output", END)
    graph.add_edge("handle_error", END)

    return graph.compile()

# Each node function:
# - Receives full state
# - Returns partial state dict (only fields it modifies)
# - Logs entry with session_id
# - Raises typed exception on unrecoverable error
# - Never swallows exceptions silently
```

### session_id threading (non-negotiable):
Every log line in every agent node must include `session_id`.
```python
logger.info("Node entered", extra={"session_id": state["session_id"], "node": "run_llm"})
```

---

## New File Specifications

### 1. `data/reference/sp_conversion.json`

```json
{
  "sp_per_hour": 0.0666,
  "hours_per_sp": 15,
  "hours_per_week": 40,
  "note": "1 SP = 15 hours. SP column in xlsx must always be formula =ROUND(0.0666*Hours,2). Never compute SP in Python."
}
```

### 2. `prompts/task_extraction_prompts.py`

Must define:
```python
TASK_EXTRACTION_SYSTEM = """
You are an RPA process analyst. You will receive a process document (PDD or SDD)
and a total effort budget in hours. Your task is to extract the complete work
breakdown of the process into activities and steps.

CRITICAL CONSTRAINT: The sum of all step weights WHERE reusability is NOT "full"
must equal exactly {total_effort_hours} hours. This is a hard constraint.
Calibrate the granularity of your decomposition to fit this budget.

Return ONLY valid JSON. No preamble, no explanation, no markdown fences.
"""

TASK_EXTRACTION_USER = """
Process document:
{document_text}

Total effort budget: {total_effort_hours} hours
Process name: {process_name}

Extract activities and steps. For each step, assign:
- description: what the developer must build
- weight_hours: estimated build hours (float)
- reusability: "full" (already built, 0 additional effort) |
               "partial" (shared logic, reduced effort) |
               "none" (net-new build required)

Before returning, verify: sum(weight_hours for steps where reusability != "full")
equals {total_effort_hours}. If not, rebalance weights until it does.

Required JSON structure:
{{
  "activities": [
    {{
      "name": "activity name",
      "steps": [
        {{
          "description": "step description",
          "weight_hours": 2.0,
          "reusability": "none"
        }}
      ]
    }}
  ],
  "total_net_hours": <sum of non-full-reuse steps>,
  "verification_passed": true
}}
"""
```

### 3. `agents/task_extraction_agent.py`

StateGraph with nodes:
- `load_document` — reads stored document text from uploaded_files path
- `extract_tasks` — calls Sonnet with task_extraction prompt
- `validate_sum` — verifies `total_net_hours == total_effort_hours` (±0.5h tolerance)
- `correct_sum` — if validation fails, calls Sonnet again with correction instruction
  (max 2 retries, then raise `AgentExecutionError`)
- `store_result` — writes task_extraction JSON to s3_inputs in DB

```python
class TaskExtractionState(TypedDict):
    session_id: str
    use_case_id: str
    document_text: str
    total_effort_hours: float
    process_name: str
    task_extraction: dict | None
    validation_attempts: int
    error: str | None
```

Edges:
```
load_document → extract_tasks → validate_sum
validate_sum  → store_result   (if verification_passed and sum matches)
validate_sum  → correct_sum    (if sum mismatch, attempts < 2)
validate_sum  → handle_error   (if attempts >= 2)
correct_sum   → validate_sum
store_result  → END
handle_error  → END
```

### 4. `tools/output/tracker_sequencer.py`

Pure Python, no LLM. Input:
```python
class SequencerInput(BaseModel):
    tracker_rows: list[TrackerRow]   # ordered list from Stage 4 agent
    build_sit_start: date
    build_sit_end: date
    total_effort_hours: float

class TrackerRow(BaseModel):
    feature: str
    hours: float
    priority: Literal["MUST", "SHOULD"]
```

Logic:
- Total available calendar days = (build_sit_end - build_sit_start).days
- Each row gets proportional calendar allocation:
  `row_days = round((row.hours / total_effort_hours) * total_calendar_days)`
- Assign `start_date` = previous row's `end_date + 1 day`
- First row start = `build_sit_start`
- Skip weekends in date assignment (optional, configurable in phase_config)
- Return list of rows with `start_date`, `end_date` populated

Output:
```python
class SequencedRow(BaseModel):
    feature: str
    hours: float
    priority: Literal["MUST", "SHOULD"]
    start_date: date
    end_date: date
```

### 5. `tools/output/export_tool.py`

Strict xlsx template contract enforcement:

```python
FORMULA_SP = "=ROUND($C$16*Table5[[#This Row],[Hours]],2)"
FORMULA_DEV_STATUS = (
    '=IF(AND(LEN({k})>0,{d}="APPROVED"),'
    'VLOOKUP(Table5[[#This Row],[COMPLETION %]],COMPL_STATUS,2,1),"")'
)

# Columns Python writes (rows 19+, Table5):
# B: feature (str)
# C: scope — always "ORIGINAL"
# D: acceptance_status — blank
# E: start_date (date)
# F: end_date (date)
# G: SP — FORMULA_SP string
# H: hours (float)
# I: developer (str from project config)
# J: priority ("MUST" or "SHOULD")
# K: completion_pct — blank
# L: dev_status — FORMULA_DEV_STATUS string with row refs substituted
# M–O: blank

# Columns Python NEVER writes:
# Rows 8–16 (dashboard formulas) — untouched
# Row 16 cell C16 (SP conversion constant 0.0666) — untouched
# Named ranges: SP_COLUMN, STATUSES_COLUMN, PRIORITY_COLUMN,
#               COMPL_STATUS, COMPLETED, IN_PROGRESS, NOT_STARTED,
#               BLOCKER, MAJOR — all preserved from template
```

---

## Files to Create (net-new)

| File | Type | Phase |
|---|---|---|
| `data/reference/sp_conversion.json` | JSON config | Phase 1 |
| `data/templates/output_template.xlsx` | Fixed template | Phase 1 |
| `prompts/task_extraction_prompts.py` | Prompt file | Phase 2 |
| `agents/task_extraction_agent.py` | LangGraph StateGraph | Phase 2 |
| `tools/output/__init__.py` | Package | Phase 2 |
| `tools/output/tracker_sequencer.py` | Pure Python tool | Phase 2 |
| `tools/output/export_tool.py` | openpyxl wrapper | Phase 2 |
| `tools/analysis/__init__.py` | Package | Phase 1 |
| `tools/analysis/task_extraction_tool.py` | Output parser + validator | Phase 2 |
| `tests/unit/test_task_extraction_agent.py` | Unit test | Phase 2 |
| `tests/unit/test_tracker_sequencer.py` | Unit test | Phase 2 |
| `tests/unit/test_export_tool.py` | Unit test | Phase 3 |
| `tests/integration/test_stage3_two_job.py` | Integration test | Phase 3 |
| `tests/integration/test_stage4_hour_sum.py` | Integration test | Phase 3 |

---

## Files to Audit and Potentially Modify

| File | What to check | Risk |
|---|---|---|
| `api/v1/stage3.py` | Two-job pattern: Job B sync + Job A background dispatch | Medium |
| `services/timeline_service.py` | Does it dispatch task_extraction_agent as background? | Medium |
| `agents/tracker_agent.py` | Does it read document or receive task_extraction as input? | High |
| `prompts/tracker_prompts.py` | Does it include total_effort_hours constraint + sum verification? | High |
| `services/export_service.py` | Are SP and dev_status written as formulas, not Python values? | High |
| `tools/` root level | Duplicate files vs tools/scoring/ — consolidate | Low |
| `core/assessment/` | Empty directory — populate or delete | Low |
| `db/models.py` | Does s3_inputs JSONB include task_extraction field structure? | Medium |

---

## Files That Must NOT Be Modified

These are stable, tested, and correct. Touch nothing:

```
core/scoring/weight_matrix.py
core/scoring/classifier.py
core/scoring/effort_table.py
core/models/ (all Pydantic models)
core/exceptions.py
llm/manager.py
llm/providers/
agents/document_agent.py
agents/process_agent.py
agents/complexity_agent.py
agents/orchestrator.py
data/reference/weight_matrix.json
data/reference/effort_table.json
db/migrations/ (all existing migrations — never modify applied migrations)
```

---

## Implementation Phases

### Phase 1 — Gaps that block everything else

**1a. Add missing reference files**
```
Create: data/reference/sp_conversion.json  (content above)
Create: data/templates/output_template.xlsx
  → Must match the production template structure exactly:
    Sheet: "Feature and delivery timeline"
    Header block rows 3–16 with all dashboard formulas
    Table5 starting row 18 with correct column headers
    Named ranges: SP_COLUMN, STATUSES_COLUMN, PRIORITY_COLUMN,
                  COMPL_STATUS, COMPLETED, IN_PROGRESS, NOT_STARTED, BLOCKER, MAJOR
    Cell C16 = 0.0666 (SP conversion constant)
```

**1b. Consolidate tools/ directory**
```
Move tools/attribute_scorer.py       → tools/scoring/attribute_scorer.py (if duplicate)
Move tools/classifier_tool.py        → tools/scoring/classifier_tool.py (if duplicate)
Move tools/effort_table_tool.py      → tools/scoring/effort_table_tool.py (if duplicate)
Move tools/weighted_calculator.py    → tools/scoring/weighted_calculator.py (if duplicate)
Keep: tools/sprint_assigner.py (used by Stage 4 — audit before moving)
Create: tools/analysis/__init__.py
Create: tools/output/__init__.py
Update all imports in agents/, services/, api/ that reference moved files
Run: uv run pytest tests/ -v  ← must still pass after import updates
```

**1c. Verify or fix core/assessment/**
```
If empty: delete directory
If needed for Stage 1 logic: move relevant code here from services/assessment_service.py
```

Exit condition: `uv run pytest tests/ -v` passes with zero failures

---

### Phase 2 — New agent: Task Extraction (Stage 3 Job A)

**2a. Create prompt file**
```
Create: prompts/task_extraction_prompts.py
  - TASK_EXTRACTION_SYSTEM with total_effort_hours constraint instruction
  - TASK_EXTRACTION_USER with document_text + total_effort_hours template variables
  - Explicit sum verification instruction before responding
  - JSON-only output instruction (no fences, no preamble)
```

**2b. Create output parser + validator**
```
Create: tools/analysis/task_extraction_tool.py
  - parse_task_extraction(raw_json: str) -> TaskExtractionResult
  - validate_hour_sum(result: TaskExtractionResult, budget: float, tolerance: float = 0.5) -> bool
  - All using Pydantic models, typed exceptions on failure
  - Independently testable (no DB, no LLM dependency)
```

**2c. Create TaskExtractionAgent**
```
Create: agents/task_extraction_agent.py
  - LangGraph StateGraph with nodes: load_document, extract_tasks,
    validate_sum, correct_sum, store_result, handle_error
  - session_id threaded through all log lines
  - Max 2 correction retries, then AgentExecutionError
  - Writes result to s3_inputs["task_extraction"] in DB
  - Model: claude-sonnet-4-5 via LLMManager (reads from llm_configs DB table)
```

**2d. Create TrackerSequencer**
```
Create: tools/output/tracker_sequencer.py
  - Pure Python, zero LLM
  - Input: ordered TrackerRow list + build_sit_window + total_effort_hours
  - Proportional calendar date assignment
  - Returns SequencedRow list with start_date + end_date per row
  - Independently testable
```

**2e. Write tests**
```
Create: tests/unit/test_task_extraction_agent.py
  - Test: validate_hour_sum passes when sum matches within tolerance
  - Test: validate_hour_sum raises on sum mismatch after 2 retries
  - Test: parse_task_extraction handles malformed JSON gracefully
Create: tests/unit/test_tracker_sequencer.py
  - Test: total calendar days allocated correctly
  - Test: dates are sequential, no gaps
  - Test: first row starts on build_sit_start, last row ends on build_sit_end
```

Exit condition: new tests pass, existing tests still pass

---

### Phase 3 — Audit and fix existing Stage 3, 4, and export

**3a. Audit and fix api/v1/stage3.py**
```
Required POST /s3/runs behaviour:
1. Read s3_inputs (effort_weeks, start_date, complexity_class, document paths)
2. Run timeline_service synchronously → return phases[] + build_sit_window immediately
3. If document exists in s2_inputs: dispatch task_extraction_agent as BackgroundTask
   task_extraction_agent(use_case_id, document_path, total_effort_hours, session_id)
4. If no document: set s3_inputs["task_extraction"]["extraction_status"] = "skipped"
5. Return: {run_id, phases, build_sit_window, task_extraction_status: "pending"|"skipped"}

GET /readiness must return:
  s3_phase_calculator: "complete" | "not_ready"
  s3_task_extraction: "pending" | "complete" | "skipped" | "not_ready"
```

**3b. Audit and fix agents/tracker_agent.py**
```
Required: tracker_agent receives task_extraction (structured JSON from Stage 3)
          as its primary input — NOT the process document.

If current agent re-reads the document:
  Remove document reading from tracker_agent
  Add task_extraction as required input field in state
  Update state type: TaskExtractionState → TrackerState

StateGraph nodes required:
  validate_inputs  — confirm task_extraction + build_sit_window present
  group_steps      — Sonnet call: receive steps, group into WBS rows, verify Σhours
  validate_sum     — confirm Σ(row.hours) == total_effort_hours (±0.5h)
  sequence_dates   — call tracker_sequencer (pure Python)
  store_result     — write wbs_rows to s4_inputs in DB
  handle_error     — typed exception, log with session_id
```

**3c. Audit and fix prompts/tracker_prompts.py**
```
Required content:
  - Receive task_extraction (structured activities + steps) as input
  - Instruction: group related steps into tracker rows
  - Instruction: sum hours per group (exclude full-reuse steps)
  - HARD CONSTRAINT: Σ(row.hours) must equal total_effort_hours
  - Instruction: verify sum before responding, rebalance if needed
  - JSON-only output, no fences

If constraint language is absent: add it.
If document reading instructions present: remove them.
```

**3d. Audit and fix services/export_service.py**
```
Check each tracker row write:
  SP column (G): must write formula string "=ROUND($C$16*Table5[[#This Row],[Hours]],2)"
                 NOT a computed float value
  Dev status (L): must write VLOOKUP formula string referencing COMPL_STATUS named range
                  NOT a computed string like "IN PROGRESS"
  Rows 8–16: must not be written at all (dashboard formulas preserved from template)
  Cell C16: must not be overwritten (SP constant 0.0666 preserved from template)

If any of the above are violated: fix the write logic.
Add: export_tool.py helper (spec above) that encapsulates formula strings.
```

**3e. Write integration tests**
```
Create: tests/integration/test_stage3_two_job.py
  - POST /s3/runs with document present → timeline returned, task_extraction status pending
  - After background task completes → GET /readiness shows task_extraction: complete
  - task_extraction.total_net_hours ≈ effort_weeks * 40 (±0.5h)

Create: tests/integration/test_stage4_hour_sum.py
  - POST /s4/runs with valid task_extraction → WBS rows generated
  - sum(row.hours for row in wbs_rows) == task_extraction.total_net_hours (±0.5h)
  - GET /s4/runs/{id}/export → xlsx downloads, opens without errors
  - xlsx SP column contains formula strings not float values
```

Exit condition: all new tests pass, all existing tests still pass,
ground truth test still passes (21 → L)

---

### Phase 4 — Frontend audit and gaps

**4a. Verify Stage 3 page handles two-job state**
```
File: src/app/(app)/projects/[id]/stage3/[ucId]/page.tsx

Required states to handle:
  s3_phase_calculator: complete → show Gantt immediately
  s3_task_extraction: pending   → show "Extracting process steps..." skeleton
  s3_task_extraction: complete  → show TaskExtractionPanel (activity accordion)
  s3_task_extraction: skipped   → show "No document — enter steps manually" state

If TaskExtractionPanel component does not exist: create it.
```

**4b. Verify Stage 4 page has HourSumValidator**
```
File: src/app/(app)/projects/[id]/stage4/[ucId]/page.tsx

Required: HourSumValidator component always visible above WBS table showing:
  "Σ hours: {actual} / {budget_hours}" with green/red indicator
  Red if |actual - budget| > 0.5 hours

If missing: create HourSumValidator component.
```

**4c. Verify AgentActivityFeed is wired for new agents**
```
File: src/components/shared/AgentActivityFeed.tsx
File: src/lib/hooks/useAgentStream.ts

The new task_extraction_agent and updated tracker_agent emit SSE events.
Verify the stream hook handles these event types and the feed renders them.
If agent names differ: update event type matching.
```

---

## StateGraph Audit Checklist

Before declaring any agent complete, verify all of the following:

```
[ ] Agent is implemented as LangGraph StateGraph (not a plain async function)
[ ] State type is a TypedDict with session_id field
[ ] session_id is logged at every node entry
[ ] All LLM calls go through LLMManager, never direct anthropic client
[ ] Model selection reads from llm_configs DB table via LLMManager
[ ] All node inputs/outputs use Pydantic models, not raw dicts
[ ] Typed exceptions raised on unrecoverable errors (AgentExecutionError etc.)
[ ] No business logic in agent files — business logic lives in tools/
[ ] All prompts loaded from prompts/ files — never inline strings
[ ] Tests exist for the agent (unit and/or integration)
[ ] Ground truth test still passes after agent changes
```

Apply this checklist to:
- `agents/task_extraction_agent.py` (new)
- `agents/tracker_agent.py` (audit existing)
- `agents/project_orchestrator.py` (audit — verify session_id threading)

---

## Test Execution Order

Run tests in this order after each phase:

```bash
# After Phase 1 (tools consolidation):
uv run pytest tests/unit/test_ground_truth_scoring.py -v
uv run pytest tests/unit/test_scoring_ground_truth.py -v
uv run pytest tests/ -v

# After Phase 2 (new agents):
uv run pytest tests/unit/test_task_extraction_agent.py -v
uv run pytest tests/unit/test_tracker_sequencer.py -v
uv run pytest tests/ -v   # full suite must still pass

# After Phase 3 (audit fixes):
uv run pytest tests/integration/test_stage3_two_job.py -v
uv run pytest tests/integration/test_stage4_hour_sum.py -v
uv run pytest tests/ -v   # full suite must still pass
```

Ground truth test must pass at every phase:
`Activities XL→8, Business Rules XL→8, Layouts L→3, Interfaces S→1, Technology S→1`
`Total: 21 → Classification: L`
