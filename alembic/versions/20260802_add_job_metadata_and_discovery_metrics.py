"""add_job_metadata_and_discovery_metrics.

Revision ID: 20260802_p8
Revises: 20260730_p76
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_p8"
down_revision: str | None = "20260730_p76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("department", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("employment_type", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("remote_status", sa.String(50), nullable=True))

    op.create_table(
        "discovery_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("source_id", sa.Integer(), nullable=True, index=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("jobs_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("discovery_metrics")
    op.drop_column("jobs", "remote_status")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "department")
