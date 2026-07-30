from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.jobs import Job


class JobMatch(Base):
    """Filtering and duplicate-detection decision for one normalized job."""

    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), unique=True, nullable=False, index=True
    )
    hard_filter_ok: Mapped[bool] = mapped_column(nullable=False, default=False)
    rejection_reasons_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    duplicate_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"), nullable=True, index=True
    )
    duplicate_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duplicate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_matched_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(
        "Job",
        foreign_keys=[job_id],
        back_populates="job_match",
    )
    duplicate_job: Mapped[Job | None] = relationship(
        "Job",
        foreign_keys=[duplicate_job_id],
    )
