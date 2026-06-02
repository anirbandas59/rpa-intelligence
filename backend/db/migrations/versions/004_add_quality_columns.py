"""add quality columns to stage_runs

Revision ID: 004_quality_columns
Revises: 003_perf_indexes
Create Date: 2026-06-01

"""

import sqlalchemy as sa
from alembic import op

revision = "004_quality_columns"
down_revision = "003_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stage_runs", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column(
        "stage_runs",
        sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("stage_runs", "retry_count")
    op.drop_column("stage_runs", "quality_score")
