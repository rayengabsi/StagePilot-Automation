"""Create job discovery tables.

Revision ID: 20260730_0001
Revises: None
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_job_sources_name"),
    )
    op.create_table(
        "raw_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_raw_jobs_source_content_hash"),
    )
    op.create_index("ix_raw_jobs_external_id", "raw_jobs", ["external_id"])
    op.create_index("ix_raw_jobs_source_id", "raw_jobs", ["source_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_job_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("normalized_hash", sa.String(length=64), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["raw_job_id"], ["raw_jobs.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_job_id", name="uq_jobs_raw_job_id"),
        sa.UniqueConstraint("source_id", "normalized_hash", name="uq_jobs_source_normalized_hash"),
    )
    op.create_index("ix_jobs_external_id", "jobs", ["external_id"])
    op.create_index("ix_jobs_source_id", "jobs", ["source_id"])


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index("ix_jobs_source_id", table_name="jobs")
    op.drop_index("ix_jobs_external_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_raw_jobs_source_id", table_name="raw_jobs")
    op.drop_index("ix_raw_jobs_external_id", table_name="raw_jobs")
    op.drop_table("raw_jobs")
    op.drop_table("job_sources")
