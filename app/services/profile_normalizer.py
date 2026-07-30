from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import ClassVar

from app.domain.master_profile.entities import (
    Award,
    Certification,
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Preference,
    Project,
    Publication,
    Skill,
)
from app.domain.master_profile.enums import ProficiencyLevel


class ProfileNormalizer:
    """Normalize raw text (from a parsed resume) into a structured MasterProfile.

    This is a purely deterministic, rule-based normalizer. No AI is used.
    It extracts structured data from free-form resume text using section
    detection, keyword matching, and regex patterns.
    """

    SECTION_HEADERS: ClassVar[dict[str, list[str]]] = {
        "education": [
            "education",
            "academic background",
            "academic experience",
            "formation",
            "formation académique",
            "studies",
            "qualifications",
        ],
        "experience": [
            "experience",
            "work experience",
            "professional experience",
            "employment",
            "work history",
            "expérience",
            "expérience professionnelle",
        ],
        "projects": ["projects", "project", "personal projects", "academic projects", "projets"],
        "skills": [
            "skills",
            "technical skills",
            "core competencies",
            "compétences",
            "compétences techniques",
            "technologies",
        ],
        "languages": ["languages", "langues", "language proficiency"],
        "certifications": [
            "certifications",
            "certificates",
            "certification",
            "certifications and training",
        ],
        "summary": ["summary", "profile", "professional summary", "about me", "profil"],
        "awards": ["awards", "honors", "honours", "distinctions", "prix", "récompenses"],
        "publications": ["publications", "papers", "research", "publications et recherche"],
    }

    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    PHONE_RE = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}"
    )
    URL_RE = re.compile(r"https?://[^\s]+")
    DATE_RE = re.compile(
        r"(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{4}\b)|(\b\d{4}\b)"
    )

    def normalize(self, raw_text: str, _source_path: Path | None = None) -> MasterProfile:
        """Convert raw resume text into a normalized MasterProfile."""
        sections = self._split_sections(raw_text)
        personal_info = self._extract_personal_info(raw_text, sections.get("summary", ""))
        education = self._parse_education(sections.get("education", ""))
        experience = self._parse_experience(sections.get("experience", ""))
        projects = self._parse_projects(sections.get("projects", ""))
        skills = self._parse_skills(sections.get("skills", ""))
        languages = self._parse_languages(sections.get("languages", ""))
        certifications = self._parse_certifications(sections.get("certifications", ""))
        awards = self._parse_awards(sections.get("awards", ""))
        publications = self._parse_publications(sections.get("publications", ""))
        preferences = Preference()

        return MasterProfile(
            personal_info=personal_info,
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            languages=languages,
            certifications=certifications,
            awards=awards,
            publications=publications,
            preferences=preferences,
        )

    def _split_sections(self, text: str) -> dict[str, str]:
        """Split raw text into named sections by detecting section headers."""
        lines = text.split("\n")
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_lines: list[str] = []

        header_patterns: dict[str, re.Pattern] = {}
        for section_name, keywords in self.SECTION_HEADERS.items():
            pattern = r"^\s*(" + "|".join(re.escape(k) for k in keywords) + r")\s*[:]*\s*$"
            header_patterns[section_name] = re.compile(pattern, re.IGNORECASE)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            matched_section: str | None = None
            for section_name, pattern in header_patterns.items():
                if pattern.match(stripped):
                    matched_section = section_name
                    break
            if matched_section is not None:
                if current_section and current_lines:
                    sections[current_section] = "\n".join(current_lines)
                current_section = matched_section
                current_lines = []
            elif current_section:
                current_lines.append(stripped)

        if current_section and current_lines:
            sections[current_section] = "\n".join(current_lines)

        return sections

    NATIONALITY_KEYWORDS: ClassVar[list[str]] = [
        "tunisian",
        "french",
        "american",
        "british",
        "german",
        "spanish",
        "italian",
        "portuguese",
        "dutch",
        "belgian",
        "swiss",
        "austrian",
        "swedish",
        "norwegian",
        "danish",
        "finnish",
        "canadian",
        "australian",
        "japanese",
        "chinese",
        "indian",
        "brazilian",
        "mexican",
        "algerian",
        "moroccan",
        "egyptian",
        "senegalese",
        "ivoirian",
        "cameroonian",
        "tunisienne",
        "française",
        "americaine",
        "allemande",
    ]

    def _extract_personal_info(self, text: str, summary_text: str = "") -> PersonalInfo:
        """Extract personal information from raw text headers."""
        lines = text.split("\n")
        first_lines = [l.strip() for l in lines[:10] if l.strip()]
        name = first_lines[0] if first_lines else ""

        emails = self.EMAIL_RE.findall(text)
        phones = self.PHONE_RE.findall(text)
        urls = self.URL_RE.findall(text)

        linkedin = next((u for u in urls if "linkedin" in u.lower()), None)
        github = next((u for u in urls if "github" in u.lower()), None)
        portfolio = next(
            (u for u in urls if u not in (linkedin, github) and "linkedin" not in u.lower()),
            None,
        )

        emails_list = list(set(emails))
        phones_list = list({p.strip() for p in phones if p.strip()})

        # Nationality detection (first few lines, case-insensitive)
        first_50 = " ".join(first_lines[:20]).lower()
        nationality: str | None = None
        for kw in self.NATIONALITY_KEYWORDS:
            if kw in first_50:
                nationality = kw.capitalize()
                break

        summary = summary_text.strip() if summary_text and len(summary_text.strip()) > 20 else None

        return PersonalInfo(
            full_name=name.strip(),
            email=emails_list[0] if emails_list else None,
            phone=phones_list[0] if phones_list else None,
            nationality=nationality,
            linkedin_url=linkedin,
            github_url=github,
            portfolio_url=portfolio,
            summary=summary,
        )

    def _parse_education(self, text: str) -> tuple[Education, ...]:
        """Parse education section into structured entries."""
        if not text.strip():
            return ()
        entries: list[Education] = []
        blocks = self._split_into_blocks(text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            institution = lines[0]
            degree: str | None = None
            field: str | None = None
            dates = self._extract_dates(block)
            for line in lines[1:]:
                lower = line.lower()
                degree_keywords = [
                    "bachelor",
                    "master",
                    "phd",
                    "doctorate",
                    "licence",
                    "baccalaureate",
                    "diploma",
                    "b.s.",
                    "m.s.",
                    "b.a.",
                    "m.a.",
                    "engineer",
                    "ingenieur",
                ]
                if any(kw in lower for kw in degree_keywords):
                    degree = line
                field_keywords = [
                    "computer science",
                    "software",
                    "engineering",
                    "mathematics",
                    "physics",
                    "data science",
                    "artificial intelligence",
                    "informatique",
                    "genie logiciel",
                    "science",
                ]
                if any(kw in lower for kw in field_keywords):
                    field = line
            entries.append(
                Education(
                    institution=institution,
                    degree=degree,
                    field_of_study=field,
                    start_date=dates[0] if len(dates) > 0 else None,
                    end_date=dates[1] if len(dates) > 1 else None,
                )
            )
        return tuple(entries)

    def _parse_experience(self, text: str) -> tuple[Experience, ...]:
        if not text.strip():
            return ()
        entries: list[Experience] = []
        blocks = self._split_into_blocks(text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            company = lines[0]
            dates = self._extract_dates(block)
            title: str | None = None
            description: str | None = None
            technologies: list[str] = []
            for line in lines[1:]:
                lower = line.lower()
                if any(
                    kw in lower
                    for kw in [
                        "intern",
                        "engineer",
                        "developer",
                        "scientist",
                        "analyst",
                        "manager",
                        "consultant",
                        "assistant",
                        "fellow",
                    ]
                ):
                    title = line
                elif any(
                    kw in lower
                    for kw in [
                        "python",
                        "java",
                        "javascript",
                        "react",
                        "sql",
                        "aws",
                        "docker",
                        "kubernetes",
                    ]
                ):
                    technologies.append(line)
                else:
                    description = line
            is_current = any(kw in block.lower() for kw in ["present", "current", "now", "ongoing"])
            entries.append(
                Experience(
                    company=company,
                    title=title,
                    start_date=dates[0] if len(dates) > 0 else None,
                    end_date=dates[1] if len(dates) > 1 else None,
                    is_current=is_current,
                    description=description,
                    technologies=tuple(technologies),
                )
            )
        return tuple(entries)

    def _parse_projects(self, text: str) -> tuple[Project, ...]:
        if not text.strip():
            return ()
        entries: list[Project] = []
        blocks = self._split_into_blocks(text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            name = lines[0]
            urls = self.URL_RE.findall(block)
            technologies: list[str] = []
            description_parts: list[str] = []
            for line in lines[1:]:
                lower = line.lower()
                if any(
                    kw in lower
                    for kw in [
                        "python",
                        "java",
                        "javascript",
                        "react",
                        "sql",
                        "aws",
                        "docker",
                        "kubernetes",
                        "flask",
                        "django",
                        "node",
                        "typescript",
                        "git",
                        "api",
                        "tensorflow",
                        "pytorch",
                        "scikit",
                    ]
                ):
                    technologies.append(line)
                elif not self.URL_RE.match(line):
                    description_parts.append(line)
            entries.append(
                Project(
                    name=name,
                    description=" ".join(description_parts) if description_parts else None,
                    url=urls[0] if urls else None,
                    technologies=tuple(technologies),
                )
            )
        return tuple(entries)

    def _parse_skills(self, text: str) -> tuple[Skill, ...]:
        if not text.strip():
            return ()
        skills: list[Skill] = []
        items = re.split(r"[,;•|\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item or len(item) < 2:
                continue
            skills.append(Skill(name=item))
        return tuple(skills)

    def _parse_languages(self, text: str) -> tuple[Language, ...]:
        if not text.strip():
            return ()
        entries: list[Language] = []
        items = re.split(r"[,;\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item:
                continue
            lower = item.lower()
            proficiency: ProficiencyLevel | None = None
            for level in ProficiencyLevel:
                if level.value in lower:
                    proficiency = level
                    break
            name = item
            if proficiency:
                name = item.lower().replace(proficiency.value, "").strip().strip(",").strip()
            entries.append(
                Language(name=name.capitalize() if name else item, proficiency=proficiency)
            )
        return tuple(entries)

    def _parse_certifications(self, text: str) -> tuple[Certification, ...]:
        if not text.strip():
            return ()
        entries: list[Certification] = []
        items = re.split(r"[,;\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item:
                continue
            entries.append(Certification(name=item))
        return tuple(entries)

    def _parse_awards(self, text: str) -> tuple[Award, ...]:
        if not text.strip():
            return ()
        entries: list[Award] = []
        items = re.split(r"[,;\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item:
                continue
            entries.append(Award(name=item))
        return tuple(entries)

    def _parse_publications(self, text: str) -> tuple[Publication, ...]:
        if not text.strip():
            return ()
        entries: list[Publication] = []
        items = re.split(r"[,;\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item or len(item) < 5:
                continue
            urls = self.URL_RE.findall(item)
            entries.append(
                Publication(
                    title=item,
                    url=urls[0] if urls else None,
                )
            )
        return tuple(entries)

    def _split_into_blocks(self, text: str) -> list[str]:
        """Split section text into logical blocks (blank-line separated)."""
        blocks = re.split(r"\n\s*\n", text)
        return [b.strip() for b in blocks if b.strip()]

    def _extract_dates(self, text: str) -> list[date]:
        """Extract dates from text, returning parsed date objects."""
        matches = self.DATE_RE.findall(text)
        found: list[date] = []
        for match in matches:
            for group in match:
                if group:
                    try:
                        parts = group.split()
                        if len(parts) == 2:
                            from datetime import datetime

                            dt = datetime.strptime(group, "%b %Y")
                            found.append(dt.date())
                        elif len(parts) == 1 and group.isdigit():
                            year = int(group)
                            if 1950 <= year <= 2100:
                                found.append(date(year, 1, 1))
                    except (ValueError, IndexError):
                        continue
        return found
