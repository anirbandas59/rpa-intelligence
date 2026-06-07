"""add upload sessions table

Revision ID: 007
Revises: 006
Create Date: 2026-06-08

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

# revision identifiers, used by Alembic.
revision = "007_upload_sessions"
down_revision = "006_agent_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("columns", JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("column_mapping", JSON(), nullable=True),
        sa.Column("created_count", sa.Integer(), nullable=True),
        sa.Column("use_case_ids", JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    # Index on status for querying active sessions
    op.create_index("ix_upload_sessions_status", "upload_sessions", ["status"])

    # Index on expires_at for cleanup job
    op.create_index("ix_upload_sessions_expires_at", "upload_sessions", ["expires_at"])

    # Index on project_id for project-level queries
    op.create_index("ix_upload_sessions_project_id", "upload_sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_project_id")
    op.drop_index("ix_upload_sessions_expires_at")
    op.drop_index("ix_upload_sessions_status")
    op.drop_table("upload_sessions")
