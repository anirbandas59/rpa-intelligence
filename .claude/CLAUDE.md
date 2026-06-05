# Claude Code Project Configuration

**See the comprehensive documentation in `/CLAUDE.md` at the repository root.**

This file is part of the `.claude/` configuration directory and can contain project-specific Claude Code settings that differ from the main documentation.

## What This Project Is

Unified web platform combining two existing RPA tools into a four-stage workflow:
- Project 1 (scripts): RPA Migration Assessment → Stage 1
- Project 2 (FastAPI + LangGraph): RPA Complexity Agent → Stage 2
- New: Stage 3 (Delivery Timeline + Task Extraction)
- New: Stage 4 (Work Breakdown Tracker + xlsx export)
- Frontend: Next.js 15 (App Router, TypeScript)

## Current Build State

The system is substantially built. The following are ALREADY IMPLEMENTED:
- All four stage API routes (api/v1/stage1-4.py)
- All Project 2 agents (document, process, complexity, orchestrator)
- LangGraph StateGraph architecture throughout
- LLM manager with multi-provider support (Anthropic, OpenAI, Ollama, WatsonX)
- Database + 6 Alembic migrations applied
- Memory system (episodic + session)
- Redis job state store + SSE streaming
- Tool registry pattern
- Frontend: all four stage pages + shared components

## What Is Missing (Gaps to Implement)

1. `data/templates/output_template.xlsx` — CRITICAL, blocks Stage 4 export
2. `data/reference/sp_conversion.json` — SP constant reference file
3. `agents/task_extraction_agent.py` — Stage 3 Job A (NEW, LangGraph StateGraph)
4. `prompts/task_extraction_prompts.py` — prompt for Stage 3 Job A
5. `tools/analysis/task_extraction_tool.py` — output parser + hour sum validator
6. `tools/output/tracker_sequencer.py` — deterministic date assignment tool
7. `tools/output/export_tool.py` — xlsx formula contract enforcement
8. `tools/` directory consolidation — duplicates at root vs tools/scoring/

## Canonical Data Chain

```
PDD/SDD → Stage 2 (Haiku, BAND LEVEL only)
         → complexity class + effort_min/max weeks
                     ↓
         Stage 3 Job B (pure Python, sync):
           effort_weeks + start_date → six phases
           Build+SIT window = tracker date range
         Stage 3 Job A (Sonnet, async background):
           document text + total_effort_hours → activities/steps/weights/reusability
           CONSTRAINT: Σ(weight_hours where reusability≠full) == total_effort_hours
                     ↓
         Stage 4 (Sonnet):
           receives task_extraction from Stage 3 (NOT the document)
           groups steps → WBS rows
           CONSTRAINT: Σ(row.hours) == total_effort_hours
                     ↓
         TrackerSequencer (pure Python):
           assigns start/end dates within Build+SIT window
                     ↓
         openpyxl fills output_template.xlsx
         SP column = formula =ROUND($C$16*Hours,2) — NEVER Python value
         Dev Status = VLOOKUP formula — NEVER Python value
         Dashboard rows 8–16 = untouched from template
```

## Repo Layout

```
rpa-intelligence/
  backend/    → FastAPI (Python 3.11, UV)
  frontend/   → Next.js 15 (TypeScript)
```

## How to Run

```bash
cd backend && uv run uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev
cd backend && uv run pytest tests/ -v
```

## NON-NEGOTIABLE RULES

1. `core/scoring/` NEVER calls LLM — pure Python math only
2. Business logic NEVER in agent files — agents call tools, tools hold logic
3. ALL prompts in `prompts/` files — never inline strings in agents or tools
4. Every tool independently importable and testable — no circular imports
5. All inputs/outputs use Pydantic models — no raw dicts as interfaces
6. Always `uv run` — never bare `python` or `python3`
7. Log EVERY agent node transition with `session_id` in structured log
8. Fail loudly with typed exceptions — never return None silently
9. All LLM calls through LLMManager — never direct anthropic/openai client
10. SP column in xlsx = ALWAYS formula `=ROUND($C$16*Hours,2)` — never Python value
11. Dev Status in xlsx = ALWAYS VLOOKUP formula — never Python value
12. Stage 3 Job A prompt MUST enforce: Σ(step weights where reusability≠full) == total_effort_hours
13. Stage 4 prompt MUST enforce: Σ(tracker row hours) == total_effort_hours
14. Never modify applied Alembic migrations (versions/001–006)
15. Never modify output_template.xlsx — it is the fixed template, only read from

## StateGraph Architecture (mandatory for all AI agents)

Every AI agent must be a LangGraph StateGraph. No direct LLM calls outside nodes.

Required state structure:
```python
class AgentState(TypedDict):
    session_id: str      # threaded through ALL log lines
    use_case_id: str
    inputs: dict
    result: dict | None
    error: str | None
```

Required node pattern:
```python
def node_name(state: AgentState) -> dict:
    logger.info("node entered", extra={"session_id": state["session_id"], "node": "node_name"})
    # ... logic using tools only ...
    return {"result": ...}   # return only modified fields
```

## Stage 3 Two-Job Pattern

`POST /s3/runs` must:
1. Run Job B (phase calculator) synchronously — return timeline immediately in response
2. Dispatch Job A (task_extraction_agent) as FastAPI BackgroundTask
3. If no document: set task_extraction.extraction_status = "skipped", skip Job A

`GET /readiness` must expose:
- `s3_phase_calculator`: "complete" | "not_ready"
- `s3_task_extraction`: "pending" | "complete" | "skipped" | "not_ready"

Stage 4 `not_ready` until `s3_task_extraction` is "complete" OR user manually enters steps.

## Stage 4 Input Source

tracker_agent receives `task_extraction` (from Stage 3 Job A result) as primary input.
It does NOT re-read the process document.
It does NOT decompose the process.
It groups existing steps into WBS rows and verifies the hour sum.

## Key Files — Do Not Modify

```
core/scoring/               ← deterministic scorer, correct and tested
core/models/                ← Pydantic models
core/exceptions.py          ← typed exception hierarchy
llm/manager.py + providers/ ← LLM abstraction
agents/document_agent.py    ← document extraction
agents/process_agent.py     ← process analysis
agents/complexity_agent.py  ← complexity assessment
agents/orchestrator.py      ← Stage 2 orchestrator
data/reference/weight_matrix.json
data/reference/effort_table.json
data/templates/output_template.xlsx  ← fixed, never modify
db/migrations/versions/001–006       ← applied migrations, never modify
```

## SP Conversion Constant

1 hour = 0.0666 SP (1 SP ≈ 15 hours)
Source: `data/reference/sp_conversion.json`
Used only in xlsx formula. Never compute SP in Python.

## Ground Truth Test (must always pass)

Activities XL→8, Business Rules XL→8, Layouts L→3, Interfaces S→1, Technology S→1
Total: 21 → Classification: L

Run: `uv run pytest tests/unit/test_ground_truth_scoring.py -v`
     `uv run pytest tests/unit/test_scoring_ground_truth.py -v`

## User Roles

user:       projects, use-cases, all stages, project-level weights + phase config
superuser:  + LLM config, prompt variants, global defaults, user management

## Git Conventions

Branches: `main` (stable), `dev` (all work)
Format: `type(scope): description`
Types: feat | fix | test | refactor | docs | chore
