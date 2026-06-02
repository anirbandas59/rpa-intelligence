"""add agent_memories table

Revision ID: 005_agent_memory
Revises: 004_quality_columns
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

revision = "005_agent_memory"
down_revision = "004_quality_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("use_case_id", sa.String(), sa.ForeignKey("use_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("content", JSON(), nullable=False),
        sa.Column("keywords", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_memories_uc", "agent_memories", ["use_case_id"])
    op.create_index("ix_agent_memories_project", "agent_memories", ["project_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_project", table_name="agent_memories")
    op.drop_index("ix_agent_memories_uc", table_name="agent_memories")
    op.drop_table("agent_memories")
