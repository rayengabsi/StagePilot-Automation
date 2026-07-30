"""create_pipeline_runs_table.

Revision ID: 32a34eb5c804
Revises: 2a9350fa7ece
Create Date: 2026-07-30 21:35:29.331609
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "32a34eb5c804"
down_revision: str | None = "2a9350fa7ece"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running", index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("jobs_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("normalized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("below_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rendering_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rendering_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("packages_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telegram_sent", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("error_summary_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
