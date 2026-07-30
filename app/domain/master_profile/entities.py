from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.domain.master_profile.enums import InternshipDuration, ProficiencyLevel, RemotePreference


@dataclass(frozen=True, slots=True)
class PersonalInfo:
    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    nationality: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class Education:
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Experience:
    company: str
    title: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None
    technologies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    description: str | None = None
    url: str | None = None
    technologies: tuple[str, ...] = ()
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    category: str | None = None
    proficiency: ProficiencyLevel | None = None


@dataclass(frozen=True, slots=True)
class Language:
    name: str
    proficiency: ProficiencyLevel | None = None


@dataclass(frozen=True, slots=True)
class Certification:
    name: str
    issuer: str | None = None
    date: date | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Award:
    name: str
    issuer: str | None = None
    date: date | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Publication:
    title: str
    publisher: str | None = None
    date: date | None = None
    url: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Preference:
    preferred_countries: tuple[str, ...] = ()
    preferred_cities: tuple[str, ...] = ()
    remote_preference: RemotePreference = RemotePreference.ANY
    internship_duration: InternshipDuration = InternshipDuration.ANY
    preferred_technologies: tuple[str, ...] = ()
    preferred_industries: tuple[str, ...] = ()
    preferred_company_size: str | None = None
    preferred_language: str | None = None
    salary_expectation: str | None = None


@dataclass(frozen=True, slots=True)
class MasterProfile:
    personal_info: PersonalInfo
    education: tuple[Education, ...] = ()
    experience: tuple[Experience, ...] = ()
    projects: tuple[Project, ...] = ()
    skills: tuple[Skill, ...] = ()
    languages: tuple[Language, ...] = ()
    certifications: tuple[Certification, ...] = ()
    awards: tuple[Award, ...] = ()
    publications: tuple[Publication, ...] = ()
    preferences: Preference = field(default_factory=Preference)

    def to_dict(self) -> dict[str, Any]:
        return {
            "personal_info": {
                "full_name": self.personal_info.full_name,
                "email": self.personal_info.email,
                "phone": self.personal_info.phone,
                "location": self.personal_info.location,
                "nationality": self.personal_info.nationality,
                "linkedin_url": self.personal_info.linkedin_url,
                "github_url": self.personal_info.github_url,
                "portfolio_url": self.personal_info.portfolio_url,
                "summary": self.personal_info.summary,
            },
            "education": [
                {
                    "institution": e.institution,
                    "degree": e.degree,
                    "field_of_study": e.field_of_study,
                    "start_date": str(e.start_date) if e.start_date else None,
                    "end_date": str(e.end_date) if e.end_date else None,
                    "gpa": e.gpa,
                    "description": e.description,
                }
                for e in self.education
            ],
            "experience": [
                {
                    "company": e.company,
                    "title": e.title,
                    "location": e.location,
                    "start_date": str(e.start_date) if e.start_date else None,
                    "end_date": str(e.end_date) if e.end_date else None,
                    "is_current": e.is_current,
                    "description": e.description,
                    "technologies": list(e.technologies),
                }
                for e in self.experience
            ],
            "projects": [
                {
                    "name": p.name,
                    "description": p.description,
                    "url": p.url,
                    "technologies": list(p.technologies),
                    "start_date": str(p.start_date) if p.start_date else None,
                    "end_date": str(p.end_date) if p.end_date else None,
                }
                for p in self.projects
            ],
            "skills": [
                {
                    "name": s.name,
                    "category": s.category,
                    "proficiency": s.proficiency.value if s.proficiency else None,
                }
                for s in self.skills
            ],
            "languages": [
                {
                    "name": l.name,
                    "proficiency": l.proficiency.value if l.proficiency else None,
                }
                for l in self.languages
            ],
            "certifications": [
                {
                    "name": c.name,
                    "issuer": c.issuer,
                    "date": str(c.date) if c.date else None,
                    "url": c.url,
                }
                for c in self.certifications
            ],
            "awards": [
                {
                    "name": a.name,
                    "issuer": a.issuer,
                    "date": str(a.date) if a.date else None,
                    "description": a.description,
                }
                for a in self.awards
            ],
            "publications": [
                {
                    "title": p.title,
                    "publisher": p.publisher,
                    "date": str(p.date) if p.date else None,
                    "url": p.url,
                    "description": p.description,
                }
                for p in self.publications
            ],
            "preferences": {
                "preferred_countries": list(self.preferences.preferred_countries),
                "preferred_cities": list(self.preferences.preferred_cities),
                "remote_preference": self.preferences.remote_preference.value,
                "internship_duration": self.preferences.internship_duration.value,
                "preferred_technologies": list(self.preferences.preferred_technologies),
                "preferred_industries": list(self.preferences.preferred_industries),
                "preferred_company_size": self.preferences.preferred_company_size,
                "preferred_language": self.preferences.preferred_language,
                "salary_expectation": self.preferences.salary_expectation,
            },
        }


@dataclass(frozen=True, slots=True)
class ProfileVersion:
    version_number: int
    profile: MasterProfile
    change_description: str
    completeness_score: float
    created_at: str


@dataclass(frozen=True, slots=True)
class ProfileCompleteness:
    score: float
    breakdown: dict[str, float]
    missing_fields: tuple[str, ...]
