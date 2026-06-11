# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# RPA Intelligence Platform — Project Memory

## What This Project Is

Unified web platform combining two existing RPA tools into a four-stage workflow:
- **Project 1** (scripts only): RPA Migration Assessment → Stage 1
- **Project 2** (FastAPI + LangGraph): RPA Complexity Agent → Stage 2
- **Stage 3**: Delivery Timeline — new, pure Python, no LLM
- **Stage 4**: Feature & Sprint Tracker — new, LangGraph + deterministic bin-packing
- **Frontend**: Next.js 16 App Router (replaces Project 2's Streamlit)

---

## Repo Layout

```
rpa-intelligence/
  backend/    → FastAPI (Python 3.12, UV)
  frontend/   → Next.js 16 (TypeScript, shadcn Nova, Tailwind v4)
  CLAUDE.md   → this file
```

---

## How to Run

```bash
# Backend
cd backend && uv run uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev     # localhost:3000

# Tests
cd backend && uv run pytest tests/ -v

# DB migrations
cd backend && uv run alembic upgrade head
```

---

## Environment

- Python **3.12.13** managed by UV (`.venv/` in `backend/`)
- Always use `uv run` — never bare `python` or `python3`
- `backend/.env` holds `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SECRET_KEY`
- `frontend/.env.local` holds `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Frontend: Next.js **16.2**, shadcn **Nova** preset, Tailwind **v4** (CSS-based config — no `tailwind.config.js`)

---

## NON-NEGOTIABLE RULES — Never Violate

1. `core/scoring/` **never calls an LLM** — pure Python math only
2. Business logic **never lives in agent files** — agents only call tools
3. **All LLM prompts** live in `prompts/` files — never inline in agent or tool code
4. Every tool is **independently importable and testable** — no circular imports
5. All function inputs/outputs use **Pydantic models** — no raw dicts as interfaces
6. **Fail loudly** with typed exceptions — never return `None` silently
7. Always use `uv run` — never bare `python`
8. **Log at every agent node transition** using structured logging with `session_id`
9. Tailwind v4: use **CSS variables in `globals.css`** — never `tailwind.config.js`
10. shadcn Nova: add components with `npx shadcn@latest add <component>` — never hand-write primitives
11. Always follow **Git Convention** format.

---

## Stage Architecture

Each stage is an **independent state machine**. Stages do not gate each other.

```
Stage N = input contract (minimum fields)
        + input layer (mutable, editable, sourced from file/prior stage/manual)
        + run engine (AI + deterministic, or deterministic only)
        + result layer (immutable StageRun records, versioned, never overwritten)
        + staleness flag: hash(current_inputs) != latest_run.inputs_hash
```

| Stage | Minimum input contract | Engine |
|-------|----------------------|--------|
| S1 — Migration Assessment | name + description | Haiku (parallel) |
| S2 — Complexity | doc upload OR pasted text OR manual bands | Haiku + deterministic scorer |
| S3 — Timeline | effort_weeks + start_date | Pure Python only (synchronous) |
| S4 — Sprint Tracker | sprint_count + timeline window | Sonnet + deterministic bin-packing |

---

## AI Model Assignments

| Task | Model | Pattern |
|------|-------|---------|
| S1: score use-cases | `claude-haiku-4-5` | Parallel ThreadPoolExecutor, per use-case |
| S1: follow-up questions | `claude-haiku-4-5` | Per low-confidence use-case |
| S1: backfill from S2 | `claude-sonnet-4-5` | One call, user-initiated |
| S2: extract bands from doc | `claude-haiku-4-5` | One call per document upload |
| S2: deterministic scorer | No LLM | Pure Python weight matrix |
| S3: phase calculator | No LLM | Pure Python date arithmetic |
| S3: narrative summary | `claude-sonnet-4-5` | Background task, non-blocking |
| S3: task decomposition | `claude-sonnet-4-5` | One call per run, async |
| S4: sprint assignment | No LLM | Deterministic bin-packing |

---

## Scoring Domain — Ground Truth (must always reproduce)

Weight matrix (5 attributes × 5 bands):

| Attribute       | XS | S | M | L | XL |
|-----------------|----|---|---|---|----|
| Activities      | 2  | 2 | 4 | 6 | 8  |
| Business Rules  | 2  | 2 | 4 | 6 | 8  |
| Layouts         | 1  | 1 | 2 | 3 | 4  |
| Interfaces      | 1  | 1 | 2 | 3 | 4  |
| Technology      | 1  | 1 | 2 | 3 | 4  |

Classification: XS (special: max 2 attrs, all XS) · S: 7–8 · M: 9–15 · L: 16–22 · XL: 23–28

Effort: XS=1wk · S=2–4wks · M=5wks · L=6wks · XL=8wks

**Ground truth test — must pass before any phase is complete:**
Activities XL→8, Business Rules XL→8, Layouts L→3, Interfaces S→1, Technology S→1
Total: 21 → Classification: **L**

---

## S1 Scoring Dimensions

- `technical_feasibility`: 0–40
- `migration_effort`: 0–25
- `platform_suitability`: 0–20
- `risk`: 0–15
- Priority bands (yes_threshold default 50): QUICK_WIN 75–100 · STRATEGIC 50–74 · HOLD 25–49 · DO_NOT_MIGRATE 0–24

---

## Database

- Local dev: SQLite (`backend/dev.db`)
- Production: PostgreSQL — change `DATABASE_URL` only, no code change
- ORM: SQLAlchemy 2.x async
- Migrations: Alembic (`uv run alembic upgrade head`)

---

## Cross-Stage Data Flow

Forward feeds (editable copy, tagged `_source: "from_sN"`):
- S1 → S2: process description enriches extraction context
- S2 → S3: effort_min_weeks, effort_max_weeks, complexity_class
- S2 → S4: process documents (re-read), process_steps
- S3 → S4: sprint_count, timeline_window

Reverse signals (user-initiated only):
- S3 calendar → S1: update migration_decision (one field, no re-run)
- S2 complexity → S1: backfill via Sonnet (one call, user-initiated)

Editing Stage N inputs **never modifies Stage M data**.

---

## Input Source Tags

Every input field carries a `_source` tag:
- `ai_extracted` — set by Haiku/Sonnet
- `manual` — typed by user fresh
- `corrected` — was ai_extracted, user changed it
- `from_s1` / `from_s2` / `from_s3` — copied from another stage
- `imported` — came from Excel/CSV upload

---

## Async Job Pattern (S1, S2, S4)

1. `POST /runs` → creates StageRun `status: running`, returns `{run_id, status}`
2. FastAPI `BackgroundTasks` executes LLM calls
3. Frontend polls `GET /use-cases/{id}/readiness` every 2s
4. On complete, frontend fetches `GET /runs/{run_id}` for full result

Stage 3 is **synchronous** — returns result immediately in the request handler.

---

## Typed Exception Hierarchy (`core/exceptions.py`)

```python
DocumentProcessingError
ScoringValidationError
LLMProviderError
AgentExecutionError
OutputGenerationError
```

---

## User Roles

- `user`: projects, use-cases, assessments, project-level weight edits
- `superuser`: everything above + LLM config, prompt variants, user management

JWT Bearer tokens, 24h expiry. `get_current_user()` on all protected routes.
`require_superuser()` dependency on `/api/v1/settings/*` routes.

---

## Key Files — Do Not Modify Without a Reason

```
backend/core/scoring/          ← deterministic scorer, ported from Project 2 unchanged
backend/data/reference/        ← weight_matrix.json, effort_table.json (source of truth)
backend/data/templates/        ← output_template.xlsx (3-sheet base template)
backend/prompts/               ← all LLM prompts live here, nowhere else
```

---

## Git Convention

Branch: `dev` for all development. Merge to `main` at each phase milestone via PR.

Commit format: `type(scope): description` - **no author/co-author**
Types: `feat` | `fix` | `test` | `refactor` | `docs` | `chore`

Examples:
```
feat(scoring): add weight matrix loader
test(scoring): add boundary tests for classifier
fix(parser): handle encrypted PDFs gracefully
chore(db): initial alembic migration
```

