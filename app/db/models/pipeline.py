from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineRunRecord(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    jobs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    below_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rendering_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rendering_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_sent: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
