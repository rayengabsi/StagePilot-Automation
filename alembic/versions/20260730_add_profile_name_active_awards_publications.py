"""Add name/active to profiles, create awards & publications tables.

Revision ID: 20260730_p76
Revises: 32a34eb5c804
Create Date: 2026-07-30 23:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_p76"
down_revision: str | None = "32a34eb5c804"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("name", sa.String(200), nullable=True))
    op.add_column("profiles", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "awards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "publications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("publications")
    op.drop_table("awards")
    op.drop_column("profiles", "active")
    op.drop_column("profiles", "name")
