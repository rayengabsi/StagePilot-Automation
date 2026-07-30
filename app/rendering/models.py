from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.domain.master_profile.entities import (
    Certification,
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Project,
    Skill,
)


class SectionType(StrEnum):
    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    LANGUAGES = "languages"
    CERTIFICATIONS = "certifications"
    AWARDS = "awards"
    VOLUNTEER = "volunteer"
    PUBLICATIONS = "publications"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class SectionContent:
    section_type: SectionType
    title: str
    items: list[dict[str, Any]]
    layout: str = "standard"


@dataclass(frozen=True, slots=True)
class RenderContext:
    personal_info: PersonalInfo
    education: tuple[Education, ...] = ()
    experience: tuple[Experience, ...] = ()
    projects: tuple[Project, ...] = ()
    skills: tuple[Skill, ...] = ()
    languages: tuple[Language, ...] = ()
    certifications: tuple[Certification, ...] = ()
    tailored_sections: dict[str, str] | None = None
    custom_sections: list[SectionContent] | None = None

    @classmethod
    def from_profile(
        cls,
        profile: MasterProfile,
        tailored_sections: dict[str, str] | None = None,
    ) -> RenderContext:
        return cls(
            personal_info=profile.personal_info,
            education=profile.education,
            experience=profile.experience,
            projects=profile.projects,
            skills=profile.skills,
            languages=profile.languages,
            certifications=profile.certifications,
            tailored_sections=tailored_sections,
        )


@dataclass(frozen=True, slots=True)
class CoverLetterData:
    body: str
    recipient_name: str | None = None
    company_name: str | None = None
    candidate_name: str = ""
    job_title: str = ""


@dataclass(frozen=True, slots=True)
class DocumentOutput:
    path: Path
    format: str
    page_count: int = 0
    sections_rendered: int = 0
    template_used: str = ""
    theme_used: str = ""
