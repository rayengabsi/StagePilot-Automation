"""add_job_classification_columns.

Revision ID: 20260802_p9
Revises: 20260802_p8
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_p9"
down_revision: str | None = "20260802_p8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("classification_specialization", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("classification_seniority", sa.String(50), nullable=True))
    op.add_column(
        "jobs", sa.Column("classification_employment_type", sa.String(100), nullable=True)
    )
    op.add_column("jobs", sa.Column("classification_work_mode", sa.String(50), nullable=True))
    op.add_column("jobs", sa.Column("classification_urgency", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "classification_urgency")
    op.drop_column("jobs", "classification_work_mode")
    op.drop_column("jobs", "classification_employment_type")
    op.drop_column("jobs", "classification_seniority")
    op.drop_column("jobs", "classification_specialization")
