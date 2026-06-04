# RPA Intelligence Platform — Implementation Guide

This document is the complete build guide for Claude Code.
Read `CLAUDE.md` first — it is loaded in every session and contains rules that override anything here.
This document is consumed phase by phase. Start Phase 1. Do not proceed to Phase N+1 until the exit condition for Phase N is met.

---

## Before Starting Any Phase

1. Read `CLAUDE.md` in full.
2. Confirm you are on the `dev` branch (`git branch`).
3. All Python commands use `uv run`. All JS commands run from `frontend/`.
4. After every file you write, check: does it violate any NON-NEGOTIABLE RULE in `CLAUDE.md`?

## Source File Conventions (override guide defaults)

weight_matrix.json structure: data["weights"][attribute][band]["weight"] → int
effort_table.json structure:  data["efforts"][class]["total"] → int or [min,max] in DAYS
Attribute key name:           "technology" (not "add_technology")
Effort conversion:            divide days by 5 to get weeks

---

## Phase 1 — Backend Foundation

**Goal:** Server starts, `/health` returns 200, ground truth scoring test passes.

### 1.1 — Core exceptions

Create `backend/core/exceptions.py`:

```python
class RPABaseError(Exception):
    """Base for all platform exceptions."""

class DocumentProcessingError(RPABaseError): pass
class ScoringValidationError(RPABaseError): pass
class LLMProviderError(RPABaseError): pass
class AgentExecutionError(RPABaseError): pass
class OutputGenerationError(RPABaseError): pass
```

### 1.2 — Data reference files

Create `backend/data/reference/weight_matrix.json`:

```json
{
  "activities":    {"XS": 2, "S": 2, "M": 4, "L": 6, "XL": 8},
  "business_rules":{"XS": 2, "S": 2, "M": 4, "L": 6, "XL": 8},
  "layouts":       {"XS": 1, "S": 1, "M": 2, "L": 3, "XL": 4},
  "interfaces":    {"XS": 1, "S": 1, "M": 2, "L": 3, "XL": 4},
  "technology ":{"XS": 1, "S": 1, "M": 2, "L": 3, "XL": 4}
}
```

Create `backend/data/reference/effort_table.json`:

```json
{
  "XS": {"min_weeks": 1, "max_weeks": 1, "sprints": 1},
  "S":  {"min_weeks": 2, "max_weeks": 4, "sprints": 2},
  "M":  {"min_weeks": 5, "max_weeks": 5, "sprints": 5},
  "L":  {"min_weeks": 6, "max_weeks": 6, "sprints": 6},
  "XL": {"min_weeks": 8, "max_weeks": 8, "sprints": 8}
}
```

### 1.3 — Core Pydantic models

Create `backend/core/models/__init__.py` (empty).

Create `backend/core/models/scoring.py`:

```python
from pydantic import BaseModel, Field
from typing import Literal

Band = Literal["XS", "S", "M", "L", "XL"]
ComplexityClass = Literal["XS", "S", "M", "L", "XL"]
InputSource = Literal["ai_extracted", "manual", "corrected", "from_s1", "from_s2", "from_s3", "imported"]

class AttributeBands(BaseModel):
    activities: Band
    business_rules: Band
    layouts: Band
    interfaces: Band
    technology : Band

class AttributeBandsWithSource(BaseModel):
    activities: Band
    activities_source: InputSource = "manual"
    business_rules: Band
    business_rules_source: InputSource = "manual"
    layouts: Band
    layouts_source: InputSource = "manual"
    interfaces: Band
    interfaces_source: InputSource = "manual"
    technology : Band
    add_technology_source: InputSource = "manual"

class ScoringResult(BaseModel):
    total_score: int
    complexity_class: ComplexityClass
    effort_min_weeks: int
    effort_max_weeks: int
    attribute_weights: dict[str, int]

class WeightMatrix(BaseModel):
    activities: dict[Band, int]
    business_rules: dict[Band, int]
    layouts: dict[Band, int]
    interfaces: dict[Band, int]
    technology : dict[Band, int]
```

### 1.4 — Deterministic scoring engine

Create `backend/core/scoring/__init__.py` (empty).

Create `backend/core/scoring/weight_matrix.py`:

```python
import json
from pathlib import Path
from core.exceptions import ScoringValidationError

_MATRIX_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "weight_matrix.json"

def load_weight_matrix() -> dict:
    """Load raw weight matrix from JSON. Returns nested dict keyed by attribute → band → weight int."""
    with open(_MATRIX_PATH) as f:
        data = json.load(f)
    # Flatten: {"activities": {"XS": 2, "S": 2, ...}, ...}
    return {
        attr: {band: values["weight"] for band, values in bands.items()}
        for attr, bands in data["weights"].items()
    }

def get_weight(matrix: dict, attribute: str, band: str) -> int:
    attr_weights = matrix.get(attribute)
    if attr_weights is None:
        raise ScoringValidationError(f"Unknown attribute: {attribute}")
    weight = attr_weights.get(band)
    if weight is None:
        raise ScoringValidationError(f"Unknown band '{band}' for attribute '{attribute}'")
    return weight
```

Create `backend/core/scoring/classifier.py`:

```python
from core.models.scoring import ComplexityClass
from core.exceptions import ScoringValidationError

# XS is a special case handled before numeric classification
_BANDS: list[tuple[ComplexityClass, int, int]] = [
    ("S",  7,  8),
    ("M",  9,  15),
    ("L",  16, 22),
    ("XL", 23, 28),
]

def classify(total_score: int, is_xs_special_case: bool = False) -> ComplexityClass:
    """Map total weight score to complexity class.

    XS special case: max 2 attributes selected, all in XS column.
    Caller is responsible for detecting and passing is_xs_special_case=True.
    """
    if is_xs_special_case:
        return "XS"
    for cls, lo, hi in _BANDS:
        if lo <= total_score <= hi:
            return cls
    raise ScoringValidationError(
        f"Score {total_score} does not map to any complexity class. "
        f"Valid range: 7–28 (or XS special case)."
    )
```

Create `backend/core/scoring/effort_table.py`:

```python
import json
from pathlib import Path
from core.exceptions import ScoringValidationError

_TABLE_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "effort_table.json"

_DAYS_PER_WEEK = 5

def _to_weeks(days) -> int:
    """Convert days (int or [min,max] list) to whole weeks, rounded up."""
    if isinstance(days, list):
        return round(days[1] / _DAYS_PER_WEEK)   # use max of range
    return round(days / _DAYS_PER_WEEK)

def get_effort(complexity_class: str) -> dict:
    """
    Returns {min_weeks, max_weeks, sprints} for a complexity class.
    Converts the source file's day-based values to weeks.
    S tier has [min, max] ranges for sprints — returns both.
    """
    with open(_TABLE_PATH) as f:
        data = json.load(f)

    if complexity_class not in data["efforts"]:
        raise ScoringValidationError(f"Unknown complexity class: {complexity_class}")

    row = data["efforts"][complexity_class]
    total = row["total"]
    sprints = row["sprints"]

    if isinstance(total, list):
        min_weeks = round(total[0] / _DAYS_PER_WEEK)
        max_weeks = round(total[1] / _DAYS_PER_WEEK)
    else:
        min_weeks = max_weeks = round(total / _DAYS_PER_WEEK)

    if isinstance(sprints, list):
        sprint_min, sprint_max = sprints[0], sprints[1]
    else:
        sprint_min = sprint_max = sprints

    return {
        "min_weeks": min_weeks,
        "max_weeks": max_weeks,
        "sprint_min": sprint_min,
        "sprint_max": sprint_max,
    }
```

### 1.5 — Ground truth test

Create `backend/tests/__init__.py` (empty).
Create `backend/tests/unit/__init__.py` (empty).

Create `backend/tests/unit/test_scoring_ground_truth.py`:

```python
"""
Ground truth test — must pass before any phase is considered complete.
Input:  Activities XL, Business Rules XL, Layouts L, Interfaces S, Technology S
Expected: total=21, class=L
"""
import pytest
from core.scoring.weight_matrix import load_weight_matrix, get_weight
from core.scoring.classifier import classify
from core.scoring.effort_table import get_effort
from core.models.scoring import AttributeBands

def test_ground_truth():
    matrix = load_weight_matrix()
    bands = AttributeBands(
        activities="XL",
        business_rules="XL",
        layouts="L",
        interfaces="S",
        technology ="S",
    )
    total = (
        get_weight(matrix, "activities", bands.activities) +
        get_weight(matrix, "business_rules", bands.business_rules) +
        get_weight(matrix, "layouts", bands.layouts) +
        get_weight(matrix, "interfaces", bands.interfaces) +
        get_weight(matrix, "technology ", bands.technology )
    )
    assert total == 21, f"Expected 21, got {total}"
    cls = classify(total)
    assert cls == "L", f"Expected L, got {cls}"
    effort = get_effort(cls)

    # 1 business month = 22 days, 1 business week = 5 days, 1 business days= 8 hrs.
    assert effort["min_weeks"] == 12
    assert effort["max_weeks"] == 12
    assert effort["sprint_min"] == 6
    assert effort["sprint_max"] == 6

def test_xs_special_case():
    cls = classify(total_score=4, is_xs_special_case=True)
    assert cls == "XS"

def test_classifier_boundaries():
    assert classify(7) == "S"
    assert classify(8) == "S"
    assert classify(9) == "M"
    assert classify(15) == "M"
    assert classify(16) == "L"
    assert classify(22) == "L"
    assert classify(23) == "XL"
    assert classify(28) == "XL"
```

Run the test now:
```bash
cd backend && uv run pytest tests/unit/test_scoring_ground_truth.py -v
```
**All tests must pass before continuing.**

### 1.6 — Database models

Create `backend/db/__init__.py` (empty).

Create `backend/db/session.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

class Base(DeclarativeBase):
    pass

def get_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)

def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

Create `backend/config.py`:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    secret_key: str
    access_token_expire_minutes: int = 1440

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/db/models.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON
from db.session import Base

def new_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user")  # user | superuser
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    use_cases: Mapped[list["UseCase"]] = relationship(back_populates="project")

class UseCase(Base):
    __tablename__ = "use_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_platform: Mapped[str | None] = mapped_column(String)
    install_status: Mapped[str | None] = mapped_column(String)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    s1_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s1_latest_run_id: Mapped[str | None] = mapped_column(String)
    s2_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s2_latest_run_id: Mapped[str | None] = mapped_column(String)
    s3_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s3_latest_run_id: Mapped[str | None] = mapped_column(String)
    s4_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s4_latest_run_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    project: Mapped["Project"] = relationship(back_populates="use_cases")
    stage_runs: Mapped[list["StageRun"]] = relationship(back_populates="use_case")

class StageRun(Base):
    __tablename__ = "stage_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String)  # s1 | s2 | s3 | s4
    run_number: Mapped[int] = mapped_column(Integer)
    inputs_snapshot: Mapped[dict] = mapped_column(JSON)
    inputs_hash: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    model_used: Mapped[str | None] = mapped_column(String)
    weight_config_snapshot: Mapped[dict | None] = mapped_column(JSON)
    prompt_variant_snapshot: Mapped[str | None] = mapped_column(String)
    triggered_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String, default="complete")  # running | complete | failed
    error_message: Mapped[str | None] = mapped_column(Text)
    use_case: Mapped["UseCase"] = relationship(back_populates="stage_runs")

class WeightConfig(Base):
    __tablename__ = "weight_configs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON)
    yes_threshold: Mapped[int] = mapped_column(Integer, default=50)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PhaseConfig(Base):
    __tablename__ = "phase_configs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON)
    sprint_length_weeks: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LLMConfig(Base):
    __tablename__ = "llm_configs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    stage: Mapped[str] = mapped_column(String)  # s1_scoring | s1_followup | s2_extract | s3_narrative | s4_decompose
    model: Mapped[str] = mapped_column(String)
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PromptVariant(Base):
    __tablename__ = "prompt_variants"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    stage: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### 1.7 — Alembic setup

```bash
cd backend
uv run alembic init db/migrations
```

Edit `backend/alembic.ini` — set:
```
sqlalchemy.url = sqlite+aiosqlite:///./dev.db
```

Edit `backend/db/migrations/env.py` — replace the `target_metadata` section:
```python
from db.session import Base
from db import models  # noqa: F401 — import all models so Alembic sees them
target_metadata = Base.metadata
```

Also ensure async support in `env.py` — use `run_async_migrations` pattern from Alembic's async template. The key addition at the top of `env.py`:
```python
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
```

And replace `run_migrations_online` with the async version:
```python
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

Generate and apply the first migration:
```bash
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

### 1.8 — FastAPI app

Create `backend/api/__init__.py` (empty).
Create `backend/api/routes/__init__.py` (empty).

Create `backend/api/dependencies.py`:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session_factory
from db.models import User
from auth import decode_token
from sqlalchemy import select

security = HTTPBearer()

async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

async def require_superuser(user: User = Depends(get_current_user)) -> User:
    if user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")
    return user
```

Create `backend/auth.py`:

```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.secret_key, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None
```

Create `backend/api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, projects, use_cases

app = FastAPI(title="RPA Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(use_cases.router, prefix="/api/v1/use-cases", tags=["use-cases"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

Create `backend/api/routes/auth.py` — register + login endpoints returning JWT.
Create `backend/api/routes/projects.py` — CRUD for projects.
Create `backend/api/routes/use_cases.py` — list, create, get, patch, delete.

(Implement these as standard FastAPI routers with Pydantic request/response models. Auth route returns `{access_token, token_type}`. All routes use `Depends(get_current_user)`.)

### Phase 1 exit condition

```bash
cd backend
uv run pytest tests/unit/test_scoring_ground_truth.py -v   # all pass
uv run uvicorn api.main:app --reload --port 8000            # starts cleanly
curl http://localhost:8000/health                           # {"status":"ok"}
```

Commit: `feat(backend): phase 1 — foundation, scoring engine, DB, auth`

---

## Phase 2 — Stage 1 Integration

**Goal:** `POST /api/v1/use-cases/{id}/s1/runs` produces the same output as running Project 1's `main.py` directly.

### 2.1 — LLM abstraction layer

Create `backend/llm/__init__.py` (empty).

Create `backend/llm/manager.py`:

```python
import anthropic
from config import get_settings

class LLMManager:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, model: str, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """Synchronous completion. Returns the text content of the first block."""
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    async def complete_async(self, model: str, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """Async completion using httpx-based async client."""
        async_client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        message = await async_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text
```

### 2.2 — Assessment prompts

Create `backend/prompts/__init__.py` (empty).

Create `backend/prompts/assessment_prompts.py`:

```python
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
Attributes: Activities={activities}, Business Rules={business_rules}, Layouts={layouts}, Interfaces={interfaces}, Technology={technology }

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
```

### 2.3 — Assessment service

Create `backend/services/__init__.py` (empty).

Create `backend/services/assessment_service.py`:

Key implementation notes:
- Port Project 1's JSON parsing pipeline verbatim: strip ` ```json ` fences, skip preamble before first `{`, trim postamble after last `}`, then `json.loads()`
- Port Project 1's parallel `ThreadPoolExecutor` + `threading.Lock()` pattern for bulk runs
- Replace file I/O with DB writes via the passed `AsyncSession`
- Each use-case assessment writes a `StageRun` record with `status: running` first, then updates to `complete` or `failed`
- Compute `inputs_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()`
- Use `ACTIVE_S1_SCORING_SYSTEM` / `ACTIVE_S1_SCORING_USER` from `prompts/assessment_prompts.py`
- Missing JSON fields get safe defaults: scores default to 0, decision derived from total if missing
- `run_number` = count of existing StageRuns for this use_case_id + stage + 1

### 2.4 — Stage 1 API routes

Create `backend/api/routes/stage1.py` with these endpoints:

```
PATCH  /use-cases/{id}/s1/inputs           → update s1_inputs on UseCase
POST   /use-cases/{id}/s1/runs             → create StageRun (running), fire BackgroundTask
GET    /use-cases/{id}/s1/runs             → list all S1 StageRuns for use-case
GET    /use-cases/{id}/s1/runs/{run_id}    → get single StageRun
POST   /use-cases/{id}/s1/override         → update decision/score fields, no new run (reason required)
POST   /use-cases/{id}/s1/backfill-from-s2 → fire Sonnet backfill, return suggestions (do not auto-apply)
```

Add to `backend/api/main.py`:
```python
from api.routes import stage1
app.include_router(stage1.router, prefix="/api/v1/use-cases", tags=["stage1"])
```

Also add bulk upload routes to `use_cases.py`:
```
POST /projects/{id}/use-cases/bulk-upload   → parse Excel/CSV, return column preview
POST /projects/{id}/use-cases/bulk-confirm  → accept column mapping, create use-cases
```

### 2.5 — Readiness endpoint

Add to `backend/api/routes/use_cases.py`:

```
GET /use-cases/{id}/readiness
```

Returns:
```json
{
  "s1": "complete|stale|running|ready|not_ready",
  "s2": "not_ready",
  "s3": "not_ready",
  "s4": "not_ready"
}
```

Staleness logic:
```python
is_stale = (
    latest_run is not None and
    hashlib.sha256(json.dumps(current_inputs, sort_keys=True).encode()).hexdigest()
    != latest_run.inputs_hash
)
```

### Phase 2 exit condition

```bash
# Start server
uv run uvicorn api.main:app --reload --port 8000

# Register user, create project, create use-case, trigger S1 run
# Verify: StageRun created with correct scores matching Project 1 output

uv run pytest tests/ -v   # ground truth still passes, add S1 integration test
```

Commit: `feat(stage1): phase 2 — migration assessment service + API routes`

---

## Phase 3 — Stage 2 Integration

**Goal:** Document upload → AI extraction → deterministic scoring via API. Ground truth still passes.

### 3.1 — Complexity prompts

Create `backend/prompts/complexity_prompts.py`:

```python
S2_EXTRACTION_SYSTEM = """You are an RPA process analyst. Extract complexity attributes from a process document.
Return ONLY valid JSON. No markdown, no preamble.

Attribute bands:
- activities: number of distinct automation steps (XS: 1-5, S: 6-10, M: 11-20, L: 21-40, XL: 41-60)
- business_rules: number of conditional rules/decision points (XS: 0, S: 1-2, M: 3-4, L: 4-5, XL: 5-6)
- layouts: number of distinct UI screens/forms (XS: 1, S: 2, M: 3, L: 4-6, XL: 7+)
- interfaces: number of external systems/APIs (XS: 0, S: 1-2, M: 3, L: 4, XL: 5+)
- technology : additional technology complexity (XS: none, S: simple scripts, M: moderate, L: complex, XL: very complex)

Response format:
{
  "activities": "<XS|S|M|L|XL>",
  "business_rules": "<XS|S|M|L|XL>",
  "layouts": "<XS|S|M|L|XL>",
  "interfaces": "<XS|S|M|L|XL>",
  "technology ": "<XS|S|M|L|XL>",
  "extraction_notes": "<brief notes on confidence and ambiguities>"
}"""

S2_EXTRACTION_USER = """Extract complexity attribute bands from this process document:

{document_text}"""
```

### 3.2 — Tools (attribute scorer, calculator, classifier, effort)

Create these four tools in `backend/tools/`. Each is independently importable, takes Pydantic inputs, returns Pydantic outputs, raises typed exceptions.

`backend/tools/attribute_scorer.py` — given `AttributeBands` + `WeightMatrix`, return dict of `{attribute: weight_int}`.

`backend/tools/weighted_calculator.py` — given attribute weights dict, return `total_score: int`.

`backend/tools/classifier_tool.py` — thin wrapper around `core/scoring/classifier.classify()`.

`backend/tools/effort_table_tool.py` — thin wrapper around `core/scoring/effort_table.get_effort()`.

### 3.3 — LangGraph complexity agents

Port these from Project 2 unchanged in structure. Each is a LangGraph `StateGraph`.

`backend/agents/document_agent.py` — reads uploaded file, extracts raw text via python-docx (`.docx`) or PyMuPDF (`.pdf`), returns text string.

`backend/agents/process_agent.py` — sends text to Haiku via `LLMManager`, parses JSON response into `AttributeBandsWithSource` (all sources = `ai_extracted`).

`backend/agents/complexity_agent.py` — calls the four tools in sequence: attribute_scorer → weighted_calculator → classifier_tool → effort_table_tool. Zero LLM calls.

`backend/agents/orchestrator.py` — LangGraph `StateGraph` wiring all three agents in sequence. Entry point: `run_assessment(use_case_id, document_path, session)`.

### 3.4 — Stage 2 API routes

Create `backend/api/routes/stage2.py`:

```
POST  /use-cases/{id}/s2/documents   → save file to uploads/, record UploadedFile, return file_id
POST  /use-cases/{id}/s2/text        → save pasted text to s2_inputs
PATCH /use-cases/{id}/s2/inputs      → update band values + source tags on s2_inputs
POST  /use-cases/{id}/s2/runs        → create StageRun (running), fire BackgroundTask (orchestrator)
GET   /use-cases/{id}/s2/runs        → list S2 StageRuns
GET   /use-cases/{id}/s2/runs/{run_id}
```

Manual band entry path: if `s2_inputs` contains all five bands and no document/text, run **only** the deterministic tools (skip document_agent and process_agent entirely). No LLM call.

### 3.5 — Project weight config routes

```
GET /projects/{id}/weights   → return active WeightConfig for project
PUT /projects/{id}/weights   → update (or create) WeightConfig, snapshot saved in next StageRun
```

### Phase 3 exit condition

```bash
uv run pytest tests/ -v   # ground truth passes, add S2 extraction + scoring tests

# Upload a sample .docx or .pdf
# Verify: S2 run produces AttributeBands + complexity class + effort
# Verify: manual band entry produces same scoring with no LLM call
```

Commit: `feat(stage2): phase 3 — complexity extraction + scoring pipeline`

---

## Phase 4 — Stage 3 (Timeline)

**Goal:** Deterministic phase calculator returns correct dates. No LLM required.

### 4.1 — Timeline service

Create `backend/services/timeline_service.py`:

```python
from datetime import date, timedelta
from dataclasses import dataclass

DEFAULT_BUFFERS = {
    "define":   {"weeks": 1, "complexity_adjusted": False},
    "design":   {"S": 1, "M": 1, "L": 2, "XL": 2, "XS": 1},
    "sit":      {"weeks": 1, "complexity_adjusted": False},
    "uat":      {"S": 1, "M": 1, "L": 2, "XL": 2, "XS": 1},
    "deploy":   {"weeks": 1, "complexity_adjusted": False},
}

@dataclass
class Phase:
    name: str
    start_date: date
    end_date: date
    weeks: int
    is_delta: bool = False

def calculate_timeline(
    build_weeks: int,
    start_date: date,
    complexity_class: str = "M",
    buffers: dict | None = None,
) -> list[Phase]:
    """Pure Python. Zero LLM. Returns phases list."""
    b = buffers or {}

    def buf(phase_name: str) -> int:
        if phase_name in ("define", "sit", "deploy"):
            return b.get(phase_name, DEFAULT_BUFFERS[phase_name]["weeks"])
        # complexity-adjusted phases
        default = DEFAULT_BUFFERS[phase_name].get(complexity_class, 1)
        return b.get(phase_name, default)

    phases = []
    cursor = start_date

    for name, weeks in [
        ("Define", buf("define")),
        ("Design", buf("design")),
        ("Build + Unit Testing", build_weeks),
        ("SIT", buf("sit")),
        ("UAT", buf("uat")),
        ("Deployment", buf("deploy")),
    ]:
        end = cursor + timedelta(weeks=weeks) - timedelta(days=1)
        phases.append(Phase(name=name, start_date=cursor, end_date=end, weeks=weeks))
        cursor = end + timedelta(days=1)

    return phases
```

### 4.2 — Stage 3 API routes

Create `backend/api/routes/stage3.py`:

```
PATCH /use-cases/{id}/s3/inputs         → set effort_weeks, start_date, complexity_class
POST  /use-cases/{id}/s3/runs           → calculate timeline synchronously, return phases immediately
GET   /use-cases/{id}/s3/runs
PATCH /use-cases/{id}/s3/phase-delta    → store delta (NOT a new StageRun)
POST  /use-cases/{id}/s3/reset-deltas  → clear deltas from s3_inputs
POST  /use-cases/{id}/s3/load-from-s2  → copy S2 effort_min/max + complexity_class into s3_inputs, tag _source: from_s2
```

Phase delta storage: deltas are stored in `s3_inputs.phase_deltas` as `{phase_name: delta_weeks}`. When returning a run result, apply deltas on top of calculated phases. "Reset" clears `phase_deltas` key.

Narrative: fire `BackgroundTasks` after timeline calculated. Sonnet receives phase list + use-case name + complexity class. Write narrative to `StageRun.result.narrative` when complete.

### 4.3 — Project phase config routes

```
GET /projects/{id}/phases   → return active PhaseConfig
PUT /projects/{id}/phases   → update buffer config
```

### Phase 4 exit condition

```bash
# POST /s3/runs with effort_weeks=6, start_date=2025-07-01, complexity_class=L
# Verify phases: Define 1wk, Design 2wks, Build 6wks, SIT 1wk, UAT 2wks, Deploy 1wk = 13wks total
uv run pytest tests/ -v
```

Commit: `feat(stage3): phase 4 — delivery timeline calculator`

---

## Phase 5 — Stage 4 (Sprint Tracker)

**Goal:** Feature decomposition run produces downloadable xlsx tracker.

### 5.1 — Sprint assigner tool

Create `backend/tools/sprint_assigner.py`:

```python
from pydantic import BaseModel
from core.exceptions import ScoringValidationError

SIZE_POINTS = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}

class Feature(BaseModel):
    name: str
    description: str
    size: str  # XS | S | M | L | XL
    dependencies: list[str] = []  # feature names this depends on

class SprintPlan(BaseModel):
    feature: Feature
    sprint_number: int

def assign_sprints(features: list[Feature], sprint_count: int, sprint_capacity: int = 8) -> list[SprintPlan]:
    """
    Deterministic bin-packing. Respects dependency ordering.
    sprint_capacity: story points per sprint (default 8).
    Returns features with assigned sprint numbers.
    Raises ScoringValidationError if features cannot fit in sprint_count sprints.
    """
    # Topological sort by dependencies first
    # Then greedy bin-pack into sprints respecting capacity
    ...
```

### 5.2 — Tracker agent

Create `backend/agents/tracker_agent.py` — LangGraph StateGraph:
- Node 1: read process documents from UploadedFile records (already uploaded in S2)
- Node 2: Sonnet call — decompose process into features with sizes and dependencies
- Node 3: `SprintAssigner.assign_sprints()` — deterministic bin-packing
- Node 4: write StageRun result

Prompt lives in `backend/prompts/tracker_prompts.py`.

### 5.3 — Export service

Create `backend/services/export_service.py`:

Takes a S4 StageRun result and writes a 3-sheet xlsx:
- Sheet 1 "Calculator": complexity data (mirrors Project 2 template)
- Sheet 2 "Steps": feature list with sprint assignments
- Sheet 3 "Feature and delivery timeline": Gantt-style timeline

Use `openpyxl`. Base on `data/templates/output_template.xlsx` structure.

### 5.4 — Stage 4 API routes

Create `backend/api/routes/stage4.py`:

```
PATCH /use-cases/{id}/s4/inputs              → set sprint_count, sprint_length, features overrides
POST  /use-cases/{id}/s4/runs               → create StageRun (running), fire BackgroundTask
GET   /use-cases/{id}/s4/runs
GET   /use-cases/{id}/s4/runs/{run_id}/export → stream xlsx file download
POST  /use-cases/{id}/s4/load-from-s2       → copy S2 process text/docs refs, tag _source: from_s2
POST  /use-cases/{id}/s4/load-from-s3       → copy S3 sprint_count + timeline, tag _source: from_s3
```

### Phase 5 exit condition

```bash
# Create use-case, upload a .docx, run S2, run S3, run S4
# GET /s4/runs/{id}/export → downloads valid xlsx with 3 sheets
uv run pytest tests/ -v
```

Commit: `feat(stage4): phase 5 — sprint tracker + xlsx export`

---

## Phase 6 — Cross-Stage Wiring + Staleness

**Goal:** Full end-to-end data flow works. Editing S4 inputs after copying from S2 does not touch S2 records.

### 6.1 — Staleness detection

Staleness computed on every `GET /readiness` call:

```python
import hashlib, json

def compute_inputs_hash(inputs: dict) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

def is_stale(current_inputs: dict, latest_run: StageRun | None) -> bool:
    if latest_run is None:
        return False
    return compute_inputs_hash(current_inputs) != latest_run.inputs_hash
```

### 6.2 — Load-from endpoints

All load-from endpoints follow this contract:
1. Read the source stage's latest StageRun result
2. Extract the relevant fields
3. Tag each field with `_source: "from_sN"`
4. Write to the target stage's `inputs` on the UseCase record
5. Return the updated inputs (do not trigger a run)

Copy semantics: the copied value is an independent dict. Modifying target inputs never touches source StageRun.

### 6.3 — Run history endpoint

Add to all stage route files:
```
GET /use-cases/{id}/s{N}/runs/{run_id}   → single run with full inputs_snapshot + result
```

### Phase 6 exit condition

```bash
# Full flow: create project → create use-case → S1 run → S2 run → S3 run
# → S4 load-from-s2 → S4 load-from-s3 → S4 run → export xlsx
# Verify: editing s4_inputs does not change s2 or s3 StageRun records
uv run pytest tests/ -v
```

Commit: `feat(cross-stage): phase 6 — staleness detection + load-from wiring`

---

## Phase 7 — Settings + Roles

**Goal:** Superuser-only settings routes enforced. Default LLM config and prompt variants seeded.

### 7.1 — Settings routes

Create `backend/api/routes/settings.py` (all use `Depends(require_superuser)`):

```
GET    /settings/llm           → list active LLMConfig per stage
PUT    /settings/llm           → update model/temperature/max_tokens per stage
GET    /settings/prompts       → list all PromptVariant records
POST   /settings/prompts       → create new variant
PUT    /settings/prompts/{id}  → update variant content
PUT    /settings/prompts/{id}/activate → set is_active=True, set others for same stage to False
GET    /settings/users         → list users
POST   /settings/users/invite  → create user (hashed password, send credentials out-of-band)
PATCH  /settings/users/{id}    → update role / is_active
```

### 7.2 — Seed migration

Add a second Alembic migration that inserts default rows:

```python
# Default LLM configs
stages = [
    ("s1_scoring",    "claude-haiku-4-5",   0.3, 1000),
    ("s1_followup",   "claude-haiku-4-5",   0.3, 500),
    ("s2_extract",    "claude-haiku-4-5",   0.2, 800),
    ("s3_narrative",  "claude-sonnet-4-5",  0.5, 1500),
    ("s4_decompose",  "claude-sonnet-4-5",  0.4, 2000),
]
# Insert via op.bulk_insert()
```

### Phase 7 exit condition

```bash
# Login as regular user → GET /settings/llm → 403
# Login as superuser → GET /settings/llm → 200
uv run pytest tests/ -v
```

Commit: `feat(settings): phase 7 — role-based settings + seed data`

---

## Phase 8 — Next.js Frontend

**Goal:** Full end-to-end flow working in browser. All four stages navigable. Export downloads.

### 8.1 — Foundation

`frontend/src/lib/api.ts` — typed fetch client:
```typescript
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}
```

`frontend/src/lib/types.ts` — TypeScript interfaces mirroring all backend Pydantic schemas.

`frontend/src/lib/scoring.ts` — client-side weight matrix calculator for Stage 2 live preview:
```typescript
const WEIGHTS = {
  activities:    { XS:2, S:2, M:4, L:6, XL:8 },
  business_rules:{ XS:2, S:2, M:4, L:6, XL:8 },
  layouts:       { XS:1, S:1, M:2, L:3, XL:4 },
  interfaces:    { XS:1, S:1, M:2, L:3, XL:4 },
  technology :{ XS:1, S:1, M:2, L:3, XL:4 },
}

export function calculateScore(bands: Record<string, string>): number {
  return Object.entries(bands).reduce((sum, [attr, band]) => {
    return sum + (WEIGHTS[attr as keyof typeof WEIGHTS]?.[band as keyof typeof WEIGHTS.activities] ?? 0)
  }, 0)
}

export function classifyScore(score: number, isXsSpecialCase = false): string {
  if (isXsSpecialCase) return "XS"
  if (score <= 6) return "XS"
  if (score <= 8) return "S"
  if (score <= 15) return "M"
  if (score <= 22) return "L"
  return "XL"
}
```

### 8.2 — Shared components (build these first)

These are used by all stage pages:

`InputSourceBadge.tsx` — renders ai/manual/corrected/from_sN badge. Props: `source: string`.

`StalenessIndicator.tsx` — amber pill "inputs changed — re-run to update" + optional pull banner.

`RunHistoryDrawer.tsx` — slide-in Sheet (shadcn) showing all runs for a stage. Per-run expand shows inputs_snapshot + result.

`StageCard.tsx` — hub card with status dot (not_ready/ready/running/complete/stale), summary stats, entry button.

`AsyncRunProgress.tsx` — polls `GET /readiness` every 2s while status=running. Shows progress bar + status text. Stops polling on complete/failed.

### 8.3 — Pages

Build in this order:

1. **`/app/page.tsx`** — redirect to `/projects`
2. **`/app/projects/page.tsx`** — project list + create button
3. **`/app/projects/new/page.tsx`** — create project form
4. **`/app/projects/[id]/page.tsx`** — use-case list + hub-and-spoke stage cards per use-case
5. **`/app/projects/[id]/stage1/page.tsx`** — upload or manual entry → assessment table → override form
6. **`/app/projects/[id]/stage2/[ucId]/page.tsx`** — doc upload → band editor (live score preview) → score card
7. **`/app/projects/[id]/stage3/[ucId]/page.tsx`** — effort input → Gantt with ± week controls → narrative
8. **`/app/projects/[id]/stage4/[ucId]/page.tsx`** — sprint table → feature list → export button
9. **`/app/settings/page.tsx`** — role-conditional: user sees profile + weights; superuser sees LLM config + prompts + users

### 8.4 — Tailwind v4 + Nova notes

- No `tailwind.config.js` — all theme tokens are CSS variables in `globals.css`
- Nova preset adds its own colour scale. Use `var(--color-*)` tokens, not hardcoded colours
- Add new shadcn components with: `npx shadcn@latest add <name>` (e.g. `sheet`, `table`, `select`, `drawer`)
- Never hand-write shadcn primitives — always use the add command

### 8.5 — Column mapper (Stage 1 bulk upload)

Two-step flow:
1. Drop Excel/CSV → `POST /projects/{id}/use-cases/bulk-upload` → returns `{columns: string[], preview: row[]}`
2. User maps columns to fields in `ColumnMapper.tsx` → `POST /bulk-confirm` with mapping → creates use-cases

### Phase 8 exit condition

```bash
npm run dev    # no TypeScript errors
# Full demo: login → create project → upload CMDB Excel → run S1 → upload PDD → run S2
# → run S3 → run S4 → download xlsx
```

Commit: `feat(frontend): phase 8 — Next.js full UI`

---

## Phase 9 — Polish & First Merge to Main

**Goal:** Demo-ready. Ground truth passes. `dev` merged to `main`.

### Checklist before merge

- [ ] `uv run pytest tests/ -v` — all tests pass including ground truth
- [ ] `npm run build` — no TypeScript errors, no build failures
- [ ] End-to-end test with real CMDB Excel + real PDD document
- [ ] Verify editing S4 inputs does not modify S2 records
- [ ] Verify staleness indicator appears after input edit, clears after re-run
- [ ] Verify run history drawer shows all runs for all stages
- [ ] Verify superuser can access `/settings`, regular user gets 403
- [ ] Remove any references to Project 2's Streamlit frontend
- [ ] Update `README.md` with full setup instructions

### Merge

```bash
git checkout main
git merge dev --no-ff -m "feat: initial platform release — all four stages"
git tag v0.1.0
```

---

## Quick Reference — What Never Changes

These rules apply to every line of code written in every phase:

| Rule | Where it applies |
|------|-----------------|
| `core/scoring/` never calls LLM | Any file in `core/scoring/` |
| Prompts in `prompts/` only | `services/`, `agents/`, `tools/` must import from `prompts/` |
| Pydantic models for all I/O | Every function signature |
| Typed exceptions, never None | Every error path |
| `uv run` only | Every bash command |
| Log at every agent node | Every `StateGraph` node function |
| Tailwind v4: CSS vars, no config.js | Every frontend file |
| shadcn: `npx shadcn@latest add` | Never hand-write primitives |
