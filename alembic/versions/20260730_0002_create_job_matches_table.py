"""Create job_matches table for filtering and duplicate decisions.

Revision ID: 20260730_0002
Revises: 20260730_0001
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "job_matches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("hard_filter_ok", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("rejection_reasons_json", sa.JSON(), nullable=True),
        sa.Column("duplicate_job_id", sa.Integer(), nullable=True),
        sa.Column("duplicate_strategy", sa.String(length=50), nullable=True),
        sa.Column("duplicate_confidence", sa.Float(), nullable=True),
        sa.Column("duplicate_matched_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["duplicate_job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_job_matches_job_id"),
    )
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])
    op.create_index("ix_job_matches_duplicate_job_id", "job_matches", ["duplicate_job_id"])


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index("ix_job_matches_duplicate_job_id", table_name="job_matches")
    op.drop_index("ix_job_matches_job_id", table_name="job_matches")
    op.drop_table("job_matches")
