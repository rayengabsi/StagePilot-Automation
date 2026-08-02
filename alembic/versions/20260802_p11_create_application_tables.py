"""create_application_tables.

Revision ID: 20260802_p11
Revises: 20260802_p10
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_p11"
down_revision: str | None = "20260802_p10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
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
        sa.Column("profile_version", sa.String(50), nullable=False, server_default="current"),
        sa.Column("company_name", sa.String(255), nullable=False, server_default="", index=True),
        sa.Column("job_title", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft", index=True),
        sa.Column(
            "application_package_id",
            sa.Integer(),
            sa.ForeignKey("application_packages.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("resume_path", sa.Text(), nullable=True),
        sa.Column("cover_letter_path", sa.Text(), nullable=True),
        sa.Column("labels_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
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
        "application_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_timeline_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending", index=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("outcome_type", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("application_outcomes")
    op.drop_table("application_reminders")
    op.drop_table("application_timeline_events")
    op.drop_table("application_notes")
    op.drop_table("application_events")
    op.drop_table("applications")
