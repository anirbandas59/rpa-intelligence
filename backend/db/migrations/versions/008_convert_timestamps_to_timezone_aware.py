"""convert timestamps to timezone aware

Revision ID: d61d3ca3fe5c
Revises: 007_upload_sessions
Create Date: 2026-06-11 20:02:15.777859

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d61d3ca3fe5c"
down_revision: str | Sequence[str] | None = "007_upload_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert all TIMESTAMP columns to TIMESTAMP WITH TIME ZONE."""
    # Users table
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # Projects table
    op.execute("ALTER TABLE projects ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Use cases table
    op.execute("ALTER TABLE use_cases ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE use_cases ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Stage runs table
    op.execute("ALTER TABLE stage_runs ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # Weight configs table
    op.execute("ALTER TABLE weight_configs ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # Phase configs table
    op.execute("ALTER TABLE phase_configs ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # LLM configs table
    op.execute("ALTER TABLE llm_configs ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Prompt variants table
    op.execute("ALTER TABLE prompt_variants ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # Agent memories table
    op.execute("ALTER TABLE agent_memories ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")

    # Agent sessions table
    op.execute("ALTER TABLE agent_sessions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE agent_sessions ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Upload sessions table
    op.execute("ALTER TABLE upload_sessions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE upload_sessions ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE")

    # Uploaded files table
    op.execute("ALTER TABLE uploaded_files ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    """Convert all TIMESTAMP WITH TIME ZONE columns back to TIMESTAMP."""
    # Users table
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Projects table
    op.execute("ALTER TABLE projects ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Use cases table
    op.execute("ALTER TABLE use_cases ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE use_cases ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Stage runs table
    op.execute("ALTER TABLE stage_runs ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Weight configs table
    op.execute("ALTER TABLE weight_configs ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Phase configs table
    op.execute("ALTER TABLE phase_configs ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # LLM configs table
    op.execute("ALTER TABLE llm_configs ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Prompt variants table
    op.execute("ALTER TABLE prompt_variants ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Agent memories table
    op.execute("ALTER TABLE agent_memories ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Agent sessions table
    op.execute("ALTER TABLE agent_sessions ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE agent_sessions ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Upload sessions table
    op.execute("ALTER TABLE upload_sessions ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE upload_sessions ALTER COLUMN expires_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Uploaded files table
    op.execute("ALTER TABLE uploaded_files ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
