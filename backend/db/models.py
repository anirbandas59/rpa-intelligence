"""
SQLAlchemy ORM models for RPA Intelligence Platform.

Implements the database schema for the four-stage RPA assessment workflow.
Core data architecture uses two layers per stage: mutable inputs (sN_inputs
fields on UseCase) and immutable versioned results (StageRun records). Staleness
detection via inputs_hash enables UI prompts for re-runs when inputs change.

Core entities:
- User: Authentication and role-based access (user | superuser)
- Project: Container with shared configuration (weight matrix, phase config)
- UseCase: RPA process flowing through 4 stages with independent execution
- StageRun: Immutable versioned result records with audit trail
- WeightConfig, PhaseConfig, LLMConfig: Project/global configuration overrides
- AgentMemory, AgentSession: Agent learning and autonomous execution tracking
- UploadedFile: S2 document upload metadata

Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_URL configuration.
All IDs are UUIDs, all timestamps use UTC, all deletions cascade appropriately.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def new_uuid() -> str:
    """Generate a new UUID string for use as primary key."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Generate a timezone-aware UTC datetime for use as default timestamp."""
    return datetime.now(UTC)


class User(Base):
    """
    User account with JWT-based authentication.

    Supports two roles: "user" (can access projects, use-cases, assessments,
    project-level configurations) and "superuser" (additionally can manage
    LLM config, prompt variants, and user accounts). In dev mode (empty
    SECRET_KEY), authentication is bypassed and dev@localhost is auto-created.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)  # bcrypt hash
    role: Mapped[str] = mapped_column(String, default="user")  # user | superuser
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # soft delete flag
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Project(Base):
    """
    Container for use cases with shared configuration.

    Groups related RPA processes under a common project (e.g., "Q1 2026 Migration").
    Can override default weight matrix and phase configuration at project level.
    Cascade deletes all child use cases, stage runs, and configurations when deleted.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "Q1 2026 Migration"
    description: Mapped[str | None] = mapped_column(Text)  # Project goals, scope, timeline
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    use_cases: Mapped[list["UseCase"]] = relationship(back_populates="project")


class UseCase(Base):
    """
    RPA process flowing through 4 stages (S1: Migration, S2: Complexity, S3: Timeline, S4: Sprint).

    Core data architecture: Each stage has TWO layers:
    1. Mutable inputs (sN_inputs dict) - user-editable, can change between runs
    2. Immutable results (StageRun records via sN_latest_run_id) - versioned history

    Staleness detection: hash(sN_inputs) != latest_run.inputs_hash triggers UI re-run prompt.
    Stages are independent - editing S2 inputs doesn't auto-trigger S1/S3/S4 re-runs.
    """

    __tablename__ = "use_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "Invoice Processing Bot"
    description: Mapped[str | None] = mapped_column(Text)  # Process overview
    source_platform: Mapped[str | None] = mapped_column(String)  # e.g., "UiPath", "Blue Prism"
    install_status: Mapped[str | None] = mapped_column(String)  # e.g., "Production", "UAT"
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # User-defined metadata

    # Stage 1 (Migration Assessment) data layer
    s1_inputs: Mapped[dict] = mapped_column(JSON, default=dict)  # Mutable input layer
    s1_latest_run_id: Mapped[str | None] = mapped_column(String)  # Pointer to most recent StageRun

    # Stage 2 (Complexity) data layer
    s2_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s2_latest_run_id: Mapped[str | None] = mapped_column(String)

    # Stage 3 (Timeline) data layer
    s3_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s3_latest_run_id: Mapped[str | None] = mapped_column(String)

    # Stage 4 (Sprint Tracker) data layer
    s4_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    s4_latest_run_id: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="use_cases")
    stage_runs: Mapped[list["StageRun"]] = relationship(back_populates="use_case")


class StageRun(Base):
    """
    Immutable versioned stage result with input/config snapshots.

    Enables version history ("compare run #3 vs #5"), audit trail, and A/B testing
    of prompts/configurations. Each run captures complete input state and configuration
    at execution time. Lifecycle: running → complete/failed (S1/S2/S4 async via background
    tasks; S3 synchronous). Quality scores (0.0-1.0) measure LLM output validation pass rate.
    """

    __tablename__ = "stage_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String)  # "s1" | "s2" | "s3" | "s4"
    run_number: Mapped[int] = mapped_column(Integer)  # Sequential per use_case + stage
    inputs_snapshot: Mapped[dict] = mapped_column(JSON)  # Frozen copy of inputs at exec time
    inputs_hash: Mapped[str] = mapped_column(String)  # SHA-256 hash for staleness check
    result: Mapped[dict] = mapped_column(JSON)  # Full stage output (structure varies by stage)
    model_used: Mapped[str | None] = mapped_column(String)  # e.g., "claude-haiku-4-5"
    weight_config_snapshot: Mapped[dict | None] = mapped_column(JSON)  # Weight matrix at exec
    prompt_variant_snapshot: Mapped[str | None] = mapped_column(String)  # Prompt version used
    triggered_by: Mapped[str | None] = mapped_column(String)  # User ID or "system"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(
        String, default="complete"
    )  # "running" | "complete" | "failed"
    error_message: Mapped[str | None] = mapped_column(Text)  # Stack trace or error detail
    quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # 0.0-1.0 LLM validation score
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0
    )  # LLM retry attempts during execution

    # Relationships
    use_case: Mapped["UseCase"] = relationship(back_populates="stage_runs")


class WeightConfig(Base):
    """
    Project-level 5×5 weight matrix override.

    Allows projects to customize the default weight matrix from
    data/reference/weight_matrix.json. yes_threshold (default 50) controls
    S1 priority cutoff (QUICK_WIN≥75, STRATEGIC≥50, HOLD≥25). Only one active
    config per project; changing triggers re-scoring of affected use cases.
    """

    __tablename__ = "weight_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(
        String, default="default"
    )  # e.g., "Conservative", "Aggressive"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Only one active per project
    config: Mapped[dict] = mapped_column(JSON)  # Full 5×5 weight matrix override
    yes_threshold: Mapped[int] = mapped_column(Integer, default=50)  # S1 priority cutoff
    created_by: Mapped[str | None] = mapped_column(String)  # User ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PhaseConfig(Base):
    """
    S3 timeline configuration (phase percentages + sprint length).

    Defines allocation percentages for the six phases (Analysis, Design, Build,
    SIT, UAT, Deploy) and sprint length for timeline calculations. One active
    config per project. Default sprint length is 2 weeks.
    """

    __tablename__ = "phase_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON)  # Phase percentages and allocations
    sprint_length_weeks: Mapped[int] = mapped_column(Integer, default=2)  # Agile sprint length
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LLMConfig(Base):
    """
    LLM configuration per task (model, temperature, token limits).

    Configurable per stage task: s1_scoring, s1_followup, s2_extract, s3_narrative,
    s4_decompose. Default: Haiku (fast) for S1/S2, Sonnet (quality) for S3/S4.
    Temperature default 0.3 for consistency. One active config per stage.
    """

    __tablename__ = "llm_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    stage: Mapped[str] = mapped_column(
        String
    )  # s1_scoring | s1_followup | s2_extract | s3_narrative | s4_decompose
    model: Mapped[str] = mapped_column(String)  # e.g., "claude-sonnet-4-5"
    temperature: Mapped[float] = mapped_column(Float, default=0.3)  # 0.0-1.0
    max_tokens: Mapped[int] = mapped_column(Integer, default=1000)  # Output limit
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str | None] = mapped_column(String)  # User ID
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PromptVariant(Base):
    """
    A/B test prompts with full audit trail.

    Stores prompt variants for testing. Content structure: {system, user, examples}.
    One active variant per stage; when inactive, uses prompts/ files. Enables
    non-developer prompt refinement with version history and attribution.
    """

    __tablename__ = "prompt_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    stage: Mapped[str] = mapped_column(String)  # Stage identifier (s1, s2, s3, s4)
    name: Mapped[str] = mapped_column(String)  # e.g., "Chain-of-Thought v2"
    content: Mapped[dict] = mapped_column(JSON)  # {system, user, examples}
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String)  # User ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UploadedFile(Base):
    """
    S2 document upload metadata (actual files stored in data/temp/).

    Tracks document uploads for Stage 2 complexity extraction. Supports
    re-extraction, audit trail, and cleanup. File types: pdf, docx, txt.
    Actual file content stored on disk, only metadata in database.
    """

    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String)  # Stage that requested upload (s2)
    original_filename: Mapped[str] = mapped_column(String)  # User's filename
    stored_path: Mapped[str] = mapped_column(String)  # Path on disk
    file_type: Mapped[str] = mapped_column(String)  # e.g., "application/pdf"
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(String)  # User ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentMemory(Base):
    """
    Agent episodic memory for learning from past assessments.

    Stores outcomes, corrections, and observations from agent executions.
    Memory types: assessment_result (final outputs), extraction_outcome
    (intermediate results), correction (user feedback). Keywords enable
    similarity search to retrieve relevant context for future runs.
    """

    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    memory_type: Mapped[str] = mapped_column(
        String
    )  # assessment_result | extraction_outcome | correction
    stage: Mapped[str] = mapped_column(String)  # s1 | s2 | s3 | s4
    content: Mapped[dict] = mapped_column(JSON)  # Structured memory content
    keywords: Mapped[str] = mapped_column(String, default="")  # Space-separated for search
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentSession(Base):
    """
    Multi-stage autonomous workflow tracker (S1→S2→S3→S4).

    Enables autonomous agents to execute complete assessment workflows
    with checkpoints. Modes: autonomous (no stops) | supervised (review
    each stage). Status: running | needs_input | complete | failed.
    """

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    goal: Mapped[str] = mapped_column(String)  # e.g., "Complete full assessment"
    mode: Mapped[str] = mapped_column(String, default="autonomous")  # autonomous | supervised
    plan: Mapped[dict] = mapped_column(JSON, default=dict)  # Execution roadmap
    status: Mapped[str] = mapped_column(
        String, default="running"
    )  # running | complete | needs_input | failed
    current_step: Mapped[int] = mapped_column(Integer, default=0)  # Step index in plan
    completed_stages: Mapped[dict] = mapped_column(JSON, default=dict)  # Progress tracking
    pending_clarification: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Question for user
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UploadSession(Base):
    """
    Stateful bulk upload session tracking file → preview → mapping → processing.

    Manages server-side upload lifecycle for bulk use-case import. File uploaded
    once and stored in temp directory, parsed in chunks for memory efficiency.
    Status progression: preview → confirmed → processing → complete | failed.
    Sessions expire after 24h and are auto-deleted via cleanup job.
    """

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String)  # Original filename (e.g., "cases.csv")
    file_path: Mapped[str] = mapped_column(String)  # Stored path in temp directory
    file_size: Mapped[int] = mapped_column(Integer)  # Size in bytes
    columns: Mapped[dict] = mapped_column(JSON)  # Column names as JSON array
    row_count: Mapped[int] = mapped_column(Integer)  # Total rows in file
    status: Mapped[str] = mapped_column(
        String, default="preview"
    )  # preview | confirmed | processing | complete | failed
    column_mapping: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {name, description, source_platform, install_status}
    created_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Use cases created
    use_case_ids: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # Created use case IDs as JSON array
    error: Mapped[str | None] = mapped_column(Text, nullable=True)  # Error message if failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )  # Auto-delete after 24h (set in service)
