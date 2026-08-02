from __future__ import annotations

from enum import StrEnum


class RecommendationStatus(StrEnum):
    ACTIVE = "active"
    REJECTED = "rejected"
    APPLIED = "applied"
    ARCHIVED = "archived"


class ConfidenceLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeedbackReason(StrEnum):
    WRONG_COUNTRY = "wrong_country"
    WRONG_FIELD = "wrong_field"
    WRONG_TECHNOLOGIES = "wrong_technologies"
    TOO_SENIOR = "too_senior"
    SALARY = "salary"
    NOT_REMOTE = "not_remote"
    OTHER = "other"


class HardRule(StrEnum):
    COUNTRY = "country"
    WORK_MODE = "work_mode"
    LANGUAGE = "language"
