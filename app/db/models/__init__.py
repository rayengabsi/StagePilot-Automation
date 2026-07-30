"""SQLAlchemy ORM model registry."""

from app.db.models.ai_usage import TokenUsageRecord
from app.db.models.approval import (
    ApplicationPackageRecord,
    ApprovalCommentRecord,
    ApprovalEventRecord,
    ApprovalQueueRecord,
)
from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.matching import JobMatch
from app.db.models.pipeline import PipelineRunRecord
from app.db.models.profile import (
    AwardRecord,
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    LanguageRecord,
    PreferenceRecord,
    Profile,
    ProfileVersionRecord,
    ProjectRecord,
    PublicationRecord,
    SkillRecord,
)
from app.db.models.recommendation import RecommendationFeedbackRecord, RecommendationRecord

__all__ = [
    "ApplicationPackageRecord",
    "ApprovalCommentRecord",
    "ApprovalEventRecord",
    "ApprovalQueueRecord",
    "AwardRecord",
    "CertificationRecord",
    "EducationRecord",
    "ExperienceRecord",
    "Job",
    "JobMatch",
    "JobSource",
    "LanguageRecord",
    "PipelineRunRecord",
    "PreferenceRecord",
    "Profile",
    "ProfileVersionRecord",
    "ProjectRecord",
    "PublicationRecord",
    "RawJob",
    "RecommendationFeedbackRecord",
    "RecommendationRecord",
    "SkillRecord",
    "TokenUsageRecord",
]
