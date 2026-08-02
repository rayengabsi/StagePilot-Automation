from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.matching import JobMatch


class JobSource(Base):
    """Configured external source used for job discovery."""

    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    raw_jobs: Mapped[list[RawJob]] = relationship(back_populates="source")
    jobs: Mapped[list[Job]] = relationship(back_populates="source")


class RawJob(Base):
    """Raw job listing payload discovered from an external source."""

    __tablename__ = "raw_jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_jobs_source_content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("job_sources.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[JobSource] = relationship(back_populates="raw_jobs")
    job: Mapped[Job | None] = relationship(back_populates="raw_job")


class Job(Base):
    """Canonical normalized job listing."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("raw_job_id", name="uq_jobs_raw_job_id"),
        UniqueConstraint("source_id", "normalized_hash", name="uq_jobs_source_normalized_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    raw_job_id: Mapped[int] = mapped_column(ForeignKey("raw_jobs.id"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("job_sources.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_specialization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_work_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    raw_job: Mapped[RawJob] = relationship(back_populates="job")
    source: Mapped[JobSource] = relationship(back_populates="jobs")
    job_match: Mapped[JobMatch | None] = relationship(
        "JobMatch",
        back_populates="job",
        uselist=False,
        foreign_keys="JobMatch.job_id",
    )
