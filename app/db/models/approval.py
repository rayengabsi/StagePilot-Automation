from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApplicationPackageRecord(Base):
    __tablename__ = "application_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    documents_json: Mapped[str] = mapped_column(Text, nullable=False)
    application_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    profile_version: Mapped[str] = mapped_column(String(50), nullable=False, default="current")
    template_name: Mapped[str] = mapped_column(String(50), nullable=False, default="modern")
    theme_name: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalQueueRecord(Base):
    __tablename__ = "approval_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("application_packages.id"), nullable=False, unique=True, index=True
    )
    queue_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package: Mapped[ApplicationPackageRecord] = relationship(backref="queue_entry")


class ApprovalEventRecord(Base):
    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("application_packages.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package: Mapped[ApplicationPackageRecord] = relationship(backref="events")


class ApprovalCommentRecord(Base):
    __tablename__ = "approval_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("application_packages.id"), nullable=False, index=True
    )
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package: Mapped[ApplicationPackageRecord] = relationship(backref="comments")
