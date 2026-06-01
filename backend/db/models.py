import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
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


class AgentMemory(Base):
    __tablename__ = "agent_memories"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    memory_type: Mapped[str] = mapped_column(String)   # assessment_result | extraction_outcome | correction
    stage: Mapped[str] = mapped_column(String)          # s1 | s2 | s3 | s4
    content: Mapped[dict] = mapped_column(JSON)         # what was learned/observed
    keywords: Mapped[str] = mapped_column(String, default="")  # space-separated for similarity search
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    use_case_id: Mapped[str] = mapped_column(String, ForeignKey("use_cases.id", ondelete="CASCADE"))
    goal: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="autonomous")  # autonomous | supervised
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="running")  # running | complete | needs_input | failed
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    completed_stages: Mapped[dict] = mapped_column(JSON, default=dict)
    pending_clarification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
