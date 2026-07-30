from __future__ import annotations

from enum import StrEnum


class ProficiencyLevel(StrEnum):
    NATIVE = "native"
    FLUENT = "fluent"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"


class RemotePreference(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class InternshipDuration(StrEnum):
    ONE_MONTH = "1_month"
    TWO_MONTHS = "2_months"
    THREE_MONTHS = "3_months"
    FOUR_MONTHS = "4_months"
    FIVE_MONTHS = "5_months"
    SIX_MONTHS = "6_months"
    ANY = "any"


class SkillCategory(StrEnum):
    PROGRAMMING_LANGUAGE = "programming_language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    CLOUD = "cloud"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    OTHER = "other"
