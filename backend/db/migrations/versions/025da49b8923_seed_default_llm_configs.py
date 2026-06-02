"""seed default llm configs

Revision ID: 025da49b8923
Revises: db9c7be9e735
Create Date: 2026-05-28 15:54:23.503544

"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision: str = "025da49b8923"
down_revision: str | Sequence[str] | None = "db9c7be9e735"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed default LLM configurations."""
    # Define table structure for bulk insert
    llm_configs = table(
        "llm_configs",
        column("id", sa.String),
        column("stage", sa.String),
        column("model", sa.String),
        column("temperature", sa.Float),
        column("max_tokens", sa.Integer),
        column("is_active", sa.Boolean),
        column("updated_at", sa.DateTime),
    )

    # Default configs per stage
    default_configs = [
        {
            "id": str(uuid.uuid4()),
            "stage": "s1_scoring",
            "model": "claude-haiku-4-5",
            "temperature": 0.3,
            "max_tokens": 1000,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid.uuid4()),
            "stage": "s1_followup",
            "model": "claude-haiku-4-5",
            "temperature": 0.3,
            "max_tokens": 500,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid.uuid4()),
            "stage": "s2_extract",
            "model": "claude-haiku-4-5",
            "temperature": 0.2,
            "max_tokens": 800,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid.uuid4()),
            "stage": "s3_narrative",
            "model": "claude-sonnet-4-5",
            "temperature": 0.5,
            "max_tokens": 1500,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid.uuid4()),
            "stage": "s4_decompose",
            "model": "claude-sonnet-4-5",
            "temperature": 0.4,
            "max_tokens": 2000,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        },
    ]

    op.bulk_insert(llm_configs, default_configs)


def downgrade() -> None:
    """Remove seeded LLM configs."""
    op.execute(
        "DELETE FROM llm_configs WHERE stage IN "
        "('s1_scoring', 's1_followup', 's2_extract', 's3_narrative', 's4_decompose')"
    )
