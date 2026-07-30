from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Profile(Base):
    """Root aggregate for a candidate's master profile."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    education_collection: Mapped[list[EducationRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    experience_collection: Mapped[list[ExperienceRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    projects_collection: Mapped[list[ProjectRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    skills_collection: Mapped[list[SkillRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    languages_collection: Mapped[list[LanguageRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    certifications_collection: Mapped[list[CertificationRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    preference: Mapped[PreferenceRecord | None] = relationship(
        back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )
    versions: Mapped[list[ProfileVersionRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileVersionRecord(Base):
    """Immutable snapshot of a profile at a point in time."""

    __tablename__ = "profile_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    change_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Profile] = relationship(back_populates="versions")


class EducationRecord(Base):
    """Normalized education entry."""

    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    degree: Mapped[str | None] = mapped_column(String(100), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gpa: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="education_collection")


class ExperienceRecord(Base):
    """Normalized work experience entry."""

    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="experience_collection")


class ProjectRecord(Base):
    """Normalized project entry."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    technologies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="projects_collection")


class SkillRecord(Base):
    """Normalized skill entry."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proficiency: Mapped[str | None] = mapped_column(String(20), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="skills_collection")


class LanguageRecord(Base):
    """Normalized language entry."""

    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(20), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="languages_collection")


class CertificationRecord(Base):
    """Normalized certification entry."""

    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="certifications_collection")


class PreferenceRecord(Base):
    """User preferences separate from resume data."""

    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id"), nullable=False, unique=True, index=True
    )
    preferred_countries_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preferred_cities_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    internship_duration: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_technologies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preferred_industries_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preferred_company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_expectation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="preference")
