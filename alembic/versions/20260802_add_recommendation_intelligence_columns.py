"""add_recommendation_intelligence_columns.

Revision ID: 20260802_p10
Revises: 20260802_p9
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_p10"
down_revision: str | None = "20260802_p9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("weighted_breakdown_json", sa.JSON(), nullable=True))
    op.add_column("recommendations", sa.Column("insights_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "insights_json")
    op.drop_column("recommendations", "weighted_breakdown_json")
