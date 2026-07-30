"""create_profile_and_related_tables.

Revision ID: 5c777eb4afd5
Revises: 20260730_0002
Create Date: 2026-07-30 19:44:15.931184
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c777eb4afd5"
down_revision: str | None = "20260730_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "education",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("institution", sa.String(200), nullable=False),
        sa.Column("degree", sa.String(100), nullable=True),
        sa.Column("field_of_study", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("gpa", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "experience",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("technologies_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("technologies_json", sa.JSON(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("proficiency", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "languages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("proficiency", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "certifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("preferred_countries_json", sa.JSON(), nullable=True),
        sa.Column("preferred_cities_json", sa.JSON(), nullable=True),
        sa.Column("remote_preference", sa.String(20), nullable=True),
        sa.Column("internship_duration", sa.String(20), nullable=True),
        sa.Column("preferred_technologies_json", sa.JSON(), nullable=True),
        sa.Column("preferred_industries_json", sa.JSON(), nullable=True),
        sa.Column("preferred_company_size", sa.String(50), nullable=True),
        sa.Column("preferred_language", sa.String(50), nullable=True),
        sa.Column("salary_expectation", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "profile_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("profiles.id"), nullable=False, index=True
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("change_description", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("profile_versions")
    op.drop_table("preferences")
    op.drop_table("certifications")
    op.drop_table("languages")
    op.drop_table("skills")
    op.drop_table("projects")
    op.drop_table("experience")
    op.drop_table("education")
    op.drop_table("profiles")
