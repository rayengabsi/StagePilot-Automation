from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    ranking_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    matched_skills_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    missing_skills_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    matched_technologies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    missing_technologies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    matched_preferences_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    unmatched_preferences_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    score_breakdown_json: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    hard_rule_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hard_rule_reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    weighted_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    insights_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationFeedbackRecord(Base):
    __tablename__ = "recommendation_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recommendation: Mapped[RecommendationRecord] = relationship(backref="feedback")
