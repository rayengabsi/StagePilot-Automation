"""SQLAlchemy ORM model registry."""

from app.db.models.ai_usage import TokenUsageRecord
from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.matching import JobMatch
from app.db.models.profile import (
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    LanguageRecord,
    PreferenceRecord,
    Profile,
    ProfileVersionRecord,
    ProjectRecord,
    SkillRecord,
)
from app.db.models.recommendation import RecommendationFeedbackRecord, RecommendationRecord

__all__ = [
    "CertificationRecord",
    "EducationRecord",
    "ExperienceRecord",
    "Job",
    "JobMatch",
    "JobSource",
    "LanguageRecord",
    "PreferenceRecord",
    "Profile",
    "ProfileVersionRecord",
    "ProjectRecord",
    "RawJob",
    "RecommendationFeedbackRecord",
    "RecommendationRecord",
    "SkillRecord",
    "TokenUsageRecord",
]
