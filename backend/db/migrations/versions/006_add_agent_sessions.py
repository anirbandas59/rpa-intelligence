"""add agent_sessions table

Revision ID: 006_agent_sessions
Revises: 005_agent_memory
Create Date: 2026-06-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

revision = "006_agent_sessions"
down_revision = "005_agent_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "use_case_id",
            sa.String(),
            sa.ForeignKey("use_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="autonomous"),
        sa.Column("plan", JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_stages", JSON(), nullable=False),
        sa.Column("pending_clarification", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_sessions")
