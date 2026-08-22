"""allow long discovery error messages.

Revision ID: f0fb458b2795
Revises: 20260811_p12
Create Date: 2026-08-22 21:11:40.062073
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0fb458b2795"
down_revision: str | None = "20260811_p12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.alter_column(
        "discovery_metrics",
        "error",
        type_=sa.Text(),
        existing_type=sa.String(length=500),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert the migration."""
    op.alter_column(
        "discovery_metrics",
        "error",
        type_=sa.String(length=500),
        existing_type=sa.Text(),
        existing_nullable=True,
    )
