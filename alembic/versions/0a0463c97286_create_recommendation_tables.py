"""create_recommendation_tables.

Revision ID: 0a0463c97286
Revises: 5c777eb4afd5
Create Date: 2026-07-30 19:59:49.843266
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0a0463c97286"
down_revision: str | None = "5c777eb4afd5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("ranking_position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("matched_skills_json", sa.JSON(), nullable=True),
        sa.Column("missing_skills_json", sa.JSON(), nullable=True),
        sa.Column("matched_technologies_json", sa.JSON(), nullable=True),
        sa.Column("missing_technologies_json", sa.JSON(), nullable=True),
        sa.Column("matched_preferences_json", sa.JSON(), nullable=True),
        sa.Column("unmatched_preferences_json", sa.JSON(), nullable=True),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=True),
        sa.Column("hard_rule_passed", sa.Boolean(), nullable=False),
        sa.Column("hard_rule_reasons", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("recommendation_feedback")
    op.drop_table("recommendations")
