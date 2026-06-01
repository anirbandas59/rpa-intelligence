"""add performance indexes

Revision ID: 003_perf_indexes
Revises: 025da49b8923
Create Date: 2026-06-01

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_perf_indexes"
down_revision: Union[str, Sequence[str], None] = "025da49b8923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_stage_run_lookup", "stage_runs", ["use_case_id", "stage", "created_at"])
    op.create_index("ix_stage_run_status", "stage_runs", ["use_case_id", "stage", "status"])
    op.create_index("ix_uploaded_uc_stage", "uploaded_files", ["use_case_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_uploaded_uc_stage", table_name="uploaded_files")
    op.drop_index("ix_stage_run_status", table_name="stage_runs")
    op.drop_index("ix_stage_run_lookup", table_name="stage_runs")
