# RPA Intelligence Platform — Project Memory

## What This Project Is
Unified web platform combining two existing RPA tools:
- Project 1 (scripts): RPA Migration Assessment — Stage 1
- Project 2 (FastAPI+LangGraph): RPA Complexity Agent — Stage 2
New additions: Stage 3 (Delivery Timeline) + Stage 4 (Feature Tracker)
Frontend: Next.js 15 (replaces Streamlit)

## Repo Layout
rpa-intelligence/
  backend/    → FastAPI (Python 3.11, UV)
  frontend/   → Next.js 15 (TypeScript)

## How to Run
cd backend && uv run uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev
cd backend && uv run pytest tests/ -v

## NON-NEGOTIABLE RULES
1. core/scoring/ NEVER calls an LLM — pure Python math only
2. Business logic NEVER lives in agent files — agents only call tools
3. ALL LLM prompts live in prompts/ files — never inline
4. Every tool independently importable and testable
5. All inputs/outputs use Pydantic models — no raw dicts
6. Always use `uv run` — never bare `python`
7. Log at every agent node with session_id
8. Fail loudly with typed exceptions — never return None silently

## Stage Architecture
Each stage = independent state machine
- Minimum input contract must be satisfied (not prior stage completion)
- Input layer: mutable, editable, sourced from file/prior stage/manual
- Run engine: AI + deterministic or deterministic only
- Result layer: immutable StageRun records, versioned, never overwritten
- Staleness: hash(current_inputs) != latest_run.inputs_hash

## Stage Input Contracts
S1 needs: name + description (minimum)
S2 needs: uploaded doc OR pasted text OR manual band entry (any one)
S3 needs: effort_weeks + start_date (minimum, no LLM required)
S4 needs: sprint_count + timeline window (minimum)

## AI Model Assignments
Haiku:  S1 scoring (parallel), S1 follow-up Qs, S2 doc extraction
Sonnet: S1 backfill from S2, S3 narrative (optional), S4 feature decomposition
No LLM: S2 deterministic scorer, S3 phase calculator, S4 sprint assignment

## Database
Local dev: SQLite (dev.db in backend/)
Production: PostgreSQL (change DATABASE_URL only)
ORM: SQLAlchemy 2.x async
Migrations: Alembic

## Key Existing Files (do not modify without reason)
backend/core/scoring/          ← deterministic scorer, port from Project 2 unchanged
backend/data/reference/        ← weight_matrix.json, effort_table.json (source of truth)
backend/data/templates/        ← output_template.xlsx (3-sheet base template)

## Ground Truth Test (must always pass)
Activities XL→8, Business Rules XL→8, Layouts L→3, Interfaces S→1, Technology S→1
Total: 21 → Classification: L

## User Roles
user:       projects, use-cases, assessments, project-level weights
superuser:  + LLM config, prompts, global defaults, user management

## Git Conventions
Branches: main (stable scaffold), dev (all development)
Commits: type(scope): description - no author/co-author
Types: feat | fix | test | refactor | docs | chore
