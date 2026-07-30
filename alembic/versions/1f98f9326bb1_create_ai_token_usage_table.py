"""create_ai_token_usage_table.

Revision ID: 1f98f9326bb1
Revises: 0a0463c97286
Create Date: 2026-07-30 20:11:49.738688
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f98f9326bb1"
down_revision: str | None = "0a0463c97286"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_token_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("feature", sa.String(50), nullable=False, index=True),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_token_usage")
