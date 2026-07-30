"""create_approval_tables.

Revision ID: 2a9350fa7ece
Revises: 1f98f9326bb1
Create Date: 2026-07-30 20:47:39.428662
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a9350fa7ece"
down_revision: str | None = "1f98f9326bb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="new", index=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("documents_json", sa.Text(), nullable=False),
        sa.Column("application_hash", sa.String(64), nullable=False),
        sa.Column("profile_version", sa.String(50), nullable=False, server_default="current"),
        sa.Column("template_name", sa.String(50), nullable=False, server_default="modern"),
        sa.Column("theme_name", sa.String(50), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_hash"),
    )
    op.create_table(
        "approval_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("application_packages.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("queue_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approval_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("application_packages.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("previous_state", sa.String(30), nullable=True),
        sa.Column("new_state", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approval_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("application_packages.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("approval_comments")
    op.drop_table("approval_events")
    op.drop_table("approval_queue")
    op.drop_table("application_packages")
