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
from app.utils.normalization import (
    DEGREE_LABEL_RE,
    FIELD_KEYWORDS_PATTERN,
    TECHNOLOGY_ALIASES,
    _alias_key,
    canonical_technology,
    clean_company_name,
    detect_degree,
    is_plausible_url,
    is_work_mode,
    looks_like_role,
    normalize_email,
    normalize_url,
)
from app.utils.text_cleaning import clean as clean_text


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
            "education and training",
            "educational background",
            "academic qualifications",
        ],
        "experience": [
            "experience",
            "work experience",
            "professional experience",
            "employment",
            "employment history",
            "work history",
            "work",
            "professional background",
            "career",
            "career history",
            "relevant experience",
            "expérience",
            "expérience professionnelle",
            "expériences professionnelles",
            "parcours professionnel",
        ],
        "projects": [
            "projects",
            "project",
            "featured projects",
            "technical projects",
            "academic projects",
            "personal projects",
            "selected projects",
            "side projects",
            "project experience",
            "project work",
            "notable projects",
            "projets",
            "projets personnels",
            "projets académiques",
        ],
        "skills": [
            "skills",
            "technical skills",
            "core competencies",
            "skills and technologies",
            "technologies",
            "technical stack",
            "toolbox",
            "compétences",
            "compétences techniques",
            "technologies utilisées",
            "skills & tools",
        ],
        "languages": [
            "languages",
            "language skills",
            "spoken languages",
            "languages spoken",
            "language proficiency",
            "langues",
            "langues parlées",
        ],
        "certifications": [
            "certifications",
            "certificates",
            "certification",
            "licenses & certifications",
            "licenses and certifications",
            "licences",
            "certifications and training",
            "training",
            "professional certifications",
            "certs",
        ],
        "summary": [
            "summary",
            "professional summary",
            "personal summary",
            "profile",
            "professional profile",
            "about me",
            "about",
            "career objective",
            "objective",
            "career summary",
            "executive summary",
            "overview",
            "highlights",
            "profil",
            "résumé",
            "resume objective",
            "job objective",
        ],
        "awards": [
            "awards",
            "honors",
            "honours",
            "achievements",
            "accomplishments",
            "scholarships",
            "competitions",
            "distinctions",
            "awards and honors",
            "awards & honors",
            "awards and achievements",
            "prix",
            "récompenses",
            "distinctions honorifiques",
        ],
        "publications": [
            "publications",
            "research",
            "papers",
            "publications and research",
            "research publications",
            "papers & publications",
            "conference papers",
            "conference",
            "journal",
            "journals",
            "publications et recherche",
        ],
    }

    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    PHONE_RE = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}"
        r"[-.\s]?\d{1,4}(?:[-.\s]?\d{1,4})?"
    )
    PHONE_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
    URL_RE = re.compile(r"https?://[^\s]+")
    BARE_URL_RE = re.compile(
        r"(?:https?://)?(?:www\.)?(?:[a-zA-Z0-9-]{2,}\.)+[a-zA-Z]{2,}(?:/[^\s]*)?",
        re.IGNORECASE,
    )
    DATE_TOKEN_RE = re.compile(
        r"\b((?:jan(?:uary|vier)?|feb(?:ruary)?|févr(?:ier)?|fevr(?:ier|uary)?|"
        r"mar(?:ch)?|mars|apr(?:il)?|avr(?:il)?|may|mai|jun(?:e)?|juin|jul(?:y)?|"
        r"juill?et|aug(?:ust)?|ao[üu]t|sep(?:tember|tembre)?|oct(?:ober|obre)?|"
        r"nov(?:ember|embre)?|dec(?:ember)?|déc(?:ember)?)"
        r"\.?\s+\d{4}|\d{4})\b",
        re.IGNORECASE,
    )

    MONTHS: ClassVar[dict[str, int]] = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
        "janvier": 1,
        "fevrier": 2,
        "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8,
        "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12,
        "décembre": 12,
    }

    TECH_WORDS: ClassVar[frozenset[str]] = frozenset(
        {
            "python",
            "java",
            "javascript",
            "typescript",
            "react",
            "angular",
            "vue",
            "node.js",
            "nodejs",
            "node",
            "golang",
            "go",
            "ruby",
            "php",
            "kotlin",
            "swift",
            "c++",
            "c#",
            ".net",
            "sql",
            "mysql",
            "postgresql",
            "postgres",
            "mongodb",
            "redis",
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "k8s",
            "terraform",
            "ansible",
            "jenkins",
            "ci/cd",
            "git",
            "github",
            "gitlab",
            "django",
            "flask",
            "fastapi",
            "spring",
            "spring boot",
            "express",
            "express.js",
            "next.js",
            "nextjs",
            "react native",
            "pytorch",
            "tensorflow",
            "keras",
            "scikit-learn",
            "sklearn",
            "pandas",
            "numpy",
            "html",
            "css",
            "scss",
            "sass",
            "tailwind",
            "tailwind css",
            "bootstrap",
            "graphql",
            "rest api",
            "kafka",
            "rabbitmq",
            "elasticsearch",
            "linux",
            "unix",
            "bash",
            "powershell",
            "firebase",
            "heroku",
            "netlify",
            "vercel",
            "webpack",
            "vite",
            "redux",
            "jest",
            "cypress",
            "selenium",
            "pytest",
            "junit",
            "hadoop",
            "spark",
            "airflow",
            "databricks",
            "tableau",
            "power bi",
            "excel",
            "microservices",
            "agile",
            "scrum",
            "jira",
            "figma",
            "photoshop",
            "ml",
            "ai",
            "machine learning",
            "deep learning",
            "nlp",
        }
    )

    GPA_LABEL_RE = re.compile(
        r"\b(?:gpa|cgpa)\s*[:=]?\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    GPA_SCALE_RE = re.compile(r"\b(\d+\.\d{1,2})\s*/\s*(?:4\.0|4)\b")

    PLACE_SUFFIXES: ClassVar[frozenset[str]] = frozenset(
        {
            "view",
            "city",
            "beach",
            "springs",
            "heights",
            "grove",
            "fort",
            "lake",
            "bay",
            "hills",
            "park",
            "point",
            "ville",
            "berg",
            "burg",
            "field",
            "fields",
            "town",
            "valley",
            "ridge",
            "creek",
            "haven",
            "junction",
            "center",
            "centre",
            "plateau",
            "country",
        }
    )
    US_STATES: ClassVar[frozenset[str]] = frozenset(
        {
            "alabama",
            "alaska",
            "arizona",
            "arkansas",
            "california",
            "colorado",
            "connecticut",
            "delaware",
            "florida",
            "georgia",
            "hawaii",
            "idaho",
            "illinois",
            "indiana",
            "iowa",
            "kansas",
            "kentucky",
            "louisiana",
            "maine",
            "maryland",
            "massachusetts",
            "michigan",
            "minnesota",
            "mississippi",
            "missouri",
            "montana",
            "nebraska",
            "nevada",
            "new hampshire",
            "new jersey",
            "new mexico",
            "new york",
            "north carolina",
            "north dakota",
            "ohio",
            "oklahoma",
            "oregon",
            "pennsylvania",
            "rhode island",
            "south carolina",
            "south dakota",
            "tennessee",
            "texas",
            "utah",
            "vermont",
            "virginia",
            "washington",
            "west virginia",
            "wisconsin",
            "wyoming",
            "dc",
        }
    )
    KNOWN_PLACES: ClassVar[frozenset[str]] = frozenset(
        {
            "tunis",
            "paris",
            "london",
            "berlin",
            "milan",
            "rome",
            "madrid",
            "barcelona",
            "amsterdam",
            "brussels",
            "geneva",
            "zurich",
            "montreal",
            "toronto",
            "ottawa",
            "vancouver",
            "new york",
            "los angeles",
            "san francisco",
            "seattle",
            "chicago",
            "austin",
            "boston",
            "atlanta",
            "denver",
            "miami",
            "dubai",
            "cairo",
            "algiers",
            "casablanca",
            "rabat",
            "remote",
            "hybrid",
            "onsite",
            "on-site",
        }
    )

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

    CERT_ISSUERS: ClassVar[tuple[str, ...]] = (
        "amazon web services",
        "aws",
        "microsoft",
        "azure",
        "cisco",
        "google cloud",
        "google",
        "coursera",
        "udemy",
        "comptia",
        "comp tia",
        "oracle",
        "salesforce",
        "ibm",
        "red hat",
        "linux foundation",
        "cncf",
        "scrum",
        "pmi",
        "pmp",
        "isc2",
        "istqb",
        "ec-council",
    )

    DEGREE_DISPLAY: ClassVar[dict[str, str]] = {
        "bachelor": "Bachelor",
        "bachelor of science": "Bachelor of Science",
        "bachelor of arts": "Bachelor of Arts",
        "bachelor of engineering": "Bachelor of Engineering",
        "bachelor of technology": "Bachelor of Technology",
        "master": "Master",
        "master of science": "Master of Science",
        "master of arts": "Master of Arts",
        "master of engineering": "Master of Engineering",
        "master of business administration": "MBA",
        "phd": "PhD",
        "doctor of philosophy": "PhD",
        "doctorate": "PhD",
        "associate": "Associate",
        "licence": "Licence",
        "licentiate": "Licentiate",
        "baccalaureate": "Baccalaureate",
        "diploma": "Diploma",
        "bootcamp": "Bootcamp",
        "certificate": "Certificate",
        "certification": "Certificate",
        "b.s.": "Bachelor of Science",
        "b.sc": "Bachelor of Science",
        "m.s.": "Master of Science",
        "m.sc": "Master of Science",
        "b.a.": "Bachelor of Arts",
        "m.a.": "Master of Arts",
        "b.eng": "Bachelor of Engineering",
        "m.eng": "Master of Engineering",
        "hnd": "HND",
    }

    CONTACT_LABELS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("linkedin", "linkedin"),
        ("github", "github"),
        ("git hub", "github"),
        ("portfolio", "portfolio"),
        ("personal website", "portfolio"),
        ("personal site", "portfolio"),
        ("website", "portfolio"),
        ("web", "portfolio"),
        ("site", "portfolio"),
    )

    def normalize(self, raw_text: str, _source_path: Path | None = None) -> MasterProfile:
        """Convert raw resume text into a normalized MasterProfile."""
        text = clean_text(raw_text)
        sections = self._split_sections(text)
        personal_info = self._extract_personal_info(text, sections)
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

    # ------------------------------------------------------------------ sections

    def _compile_headers(self, keywords: list[str]) -> re.Pattern[str]:
        alternatives = "|".join(re.escape(k) for k in keywords)
        return re.compile(rf"(?:#+\s*)?(?:{alternatives})\s*[:.\-]*\s*", re.IGNORECASE)

    def _split_sections(self, text: str) -> dict[str, str]:
        """Split raw text into named sections by detecting section headers."""
        lines = text.split("\n")
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_lines: list[str] = []
        compiled: dict[str, re.Pattern[str]] = {
            name: self._compile_headers(keywords) for name, keywords in self.SECTION_HEADERS.items()
        }

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_section and current_lines:
                    current_lines.append("")
                continue
            matched_section: str | None = None
            for section_name, pattern in compiled.items():
                if pattern.fullmatch(stripped):
                    matched_section = section_name
                    break
            if matched_section is not None:
                if current_section and current_lines:
                    sections[current_section] = "\n".join(current_lines).strip("\n")
                current_section = matched_section
                current_lines = []
            elif current_section:
                current_lines.append(stripped)

        if current_section and current_lines:
            sections[current_section] = "\n".join(current_lines).strip("\n")

        return sections

    def _header_region(self, text: str) -> list[str]:
        """Return the non-empty lines that precede the first section heading."""
        compiled: dict[str, re.Pattern[str]] = {
            name: self._compile_headers(keywords) for name, keywords in self.SECTION_HEADERS.items()
        }
        header: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.fullmatch(stripped) for pattern in compiled.values()):
                break
            header.append(stripped)
        return header

    # ---------------------------------------------------------- personal info

    def _extract_personal_info(self, text: str, sections: dict[str, str]) -> PersonalInfo:
        """Extract personal information from raw text headers."""
        header = self._header_region(text)
        all_lines = [l.strip() for l in text.split("\n") if l.strip()]
        name = self._extract_name(header, all_lines)
        email = self._extract_email(text)
        phone = self._extract_phone(text)
        location = self._extract_location(header, name)
        linkedin, github, portfolio = self._extract_contact_urls(text, header)
        nationality = self._detect_nationality(header)
        summary = self._extract_summary(text, sections, name)

        return PersonalInfo(
            full_name=name,
            email=email,
            phone=phone,
            location=location,
            nationality=nationality,
            linkedin_url=linkedin,
            github_url=github,
            portfolio_url=portfolio,
            summary=summary,
        )

    def _extract_name(self, header: list[str], all_lines: list[str]) -> str:
        skip = {"curriculum vitae", "cv", "resume", "résumé", "resume/cv", "vitae"}
        for line in header:
            candidate = line.strip().strip(".:- ")
            if not candidate:
                continue
            if candidate.lower().strip(".") in skip:
                continue
            if self._is_plausible_name(candidate):
                return candidate
        for line in all_lines:
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.lower().strip(".:- ") in skip:
                continue
            if self._is_plausible_name(candidate):
                return candidate
        return header[0] if header else (all_lines[0] if all_lines else "")

    @staticmethod
    def _is_plausible_name(line: str) -> bool:
        if not line or len(line) > 60:
            return False
        if re.search(r"\d", line):
            return False
        if "@" in line or "http" in line or "www" in line:
            return False
        if looks_like_role(line):
            return False
        words = line.split()
        if not words or len(words) > 5:
            return False
        for word in words:
            if not re.search(r"[A-Za-z]", word):
                return False
        return not (len(words) == 1 and len(words[0]) < 2)

    def _extract_email(self, text: str) -> str | None:
        emails = list({normalize_email(e) for e in self.EMAIL_RE.findall(text)})
        return emails[0] if emails else None

    def _extract_location(self, header: list[str], name: str) -> str | None:
        for line in header:
            m = re.match(
                r"^(?:location|address|based in|city|residence|home)\s*:\s*(.+)$",
                line,
                re.IGNORECASE,
            )
            if m:
                return self._clean_location(m.group(1))
            if line == name:
                continue
            if self._is_location_line(line) or self._looks_like_place(line):
                return self._clean_location(line)
        return None

    @staticmethod
    def _clean_location(value: str) -> str:
        return re.sub(r"[\s]+", " ", value.strip(" ,;:|-"))

    def _is_location_line(self, line: str) -> bool:
        if re.search(r"\d", line):
            return False
        if "@" in line or "http" in line or "www" in line:
            return False
        if line.count(",") not in (1, 2):
            return False
        if looks_like_role(line):
            return False
        lower = line.lower()
        if re.search(r"\b(?:inc|llc|ltd|corp|co|gmbh|s\.?a\.?|sarl|pvt)\b", lower):
            return False
        if len(line) > 60:
            return False
        for part in line.split(","):
            part = part.strip()
            if not part or len(part.split()) > 4:
                return False
            if not re.search(r"[A-Z]", part):
                return False
        return True

    def _looks_like_place(self, line: str) -> bool:
        lower = line.strip().lower()
        if not lower or re.search(r"\d", lower):
            return False
        if "@" in lower or "http" in lower or "www" in lower:
            return False
        if looks_like_role(line):
            return False
        words = lower.split()
        if len(words) > 3:
            return False
        if lower in self.US_STATES or lower in self.KNOWN_PLACES:
            return True
        return any(lower.endswith(" " + s) or lower == s for s in self.PLACE_SUFFIXES)

    def _extract_contact_urls(
        self, text: str, header: list[str]
    ) -> tuple[str | None, str | None, str | None]:
        linkedin: str | None = None
        github: str | None = None
        portfolio_labeled: list[str] = []
        portfolio_header: list[str] = []
        portfolio_anywhere: list[str] = []

        url_text = self.EMAIL_RE.sub(" ", text)
        url_header = self.EMAIL_RE.sub(" ", "\n".join(header))

        for line in url_text.split("\n"):
            stripped = line.strip()
            for label, kind in self.CONTACT_LABELS:
                m = re.match(
                    rf"^\s*{re.escape(label)}\s*[:|\-]\s*(\S+)\s*$",
                    stripped,
                    re.IGNORECASE,
                )
                if m:
                    value = m.group(1).strip(".,;")
                    url = self._normalize_url_candidate(value)
                    if url:
                        if kind == "linkedin":
                            linkedin = linkedin or url
                        elif kind == "github":
                            github = github or url
                        else:
                            portfolio_labeled.append(url)
                    break
            for url in self._extract_all_urls(stripped):
                if "linkedin" in url:
                    linkedin = linkedin or url
                elif "github" in url:
                    github = github or url
                else:
                    portfolio_anywhere.append(url)

        for url in self._extract_all_urls(url_header):
            if "linkedin" in url or "github" in url:
                continue
            portfolio_header.append(url)

        portfolio: str | None = None
        if portfolio_labeled:
            portfolio = portfolio_labeled[0]
        elif portfolio_header:
            portfolio = portfolio_header[0]
        elif portfolio_anywhere:
            portfolio = portfolio_anywhere[0]

        return linkedin, github, portfolio

    def _normalize_url_candidate(self, value: str) -> str | None:
        if not is_plausible_url(value):
            return None
        return normalize_url(value)

    def _extract_all_urls(self, text: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for raw in self.URL_RE.findall(text) + self.BARE_URL_RE.findall(text):
            if not is_plausible_url(raw):
                continue
            url = normalize_url(raw)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _is_url_line(self, line: str) -> bool:
        if self.URL_RE.search(line):
            return True
        return any(is_plausible_url(raw) for raw in self.BARE_URL_RE.findall(line))

    def _detect_nationality(self, header: list[str]) -> str | None:
        first_50 = " ".join(header[:20]).lower()
        for kw in self.NATIONALITY_KEYWORDS:
            if kw in first_50:
                return kw.capitalize()
        return None

    def _extract_summary(self, text: str, sections: dict[str, str], name: str) -> str | None:
        summary_text = sections.get("summary", "").strip()
        if len(summary_text) >= 15:
            return summary_text
        header = self._header_region(text)
        if len(header) > 10:
            return None
        content: list[str] = []
        for line in header:
            if line == name:
                continue
            if self._is_contact_line(line):
                continue
            content.append(line)
        joined = " ".join(content).strip()
        if len(joined) >= 25:
            return joined
        return None

    def _is_contact_line(self, line: str) -> bool:
        if "@" in line or "http" in line or "www" in line:
            return True
        if self.PHONE_RE.fullmatch(line):
            return True
        if self._is_url_line(line):
            return True
        return self._is_location_line(line) or self._looks_like_place(line)

    # -------------------------------------------------------------- phone

    def _extract_phone(self, text: str) -> str | None:
        """Extract the most plausible phone number from raw resume text.

        Bare 4-digit years (e.g. ``2025``) are rejected so they never shadow a
        real phone number, and URL substrings are removed first so digit-heavy
        links (ORCID, DOIs, etc.) are never mistaken for phone numbers.
        """
        candidates: list[str] = []
        seen: set[str] = set()
        text = self.URL_RE.sub(" ", text)
        text = " ".join(raw for raw in self.BARE_URL_RE.split(text) if not is_plausible_url(raw))
        for match in self.PHONE_RE.findall(text):
            candidate = match.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if self._is_isolated_year(candidate):
                continue
            candidates.append(candidate)
        if not candidates:
            return None
        return max(candidates, key=self._phone_strength)

    @classmethod
    def _is_isolated_year(cls, candidate: str) -> bool:
        """Return True when a candidate is a bare year, not a phone number."""
        digits = re.sub(r"\D", "", candidate)
        return len(digits) == 4 and cls.PHONE_YEAR_RE.fullmatch(candidate) is not None

    @staticmethod
    def _phone_strength(candidate: str) -> tuple[int, int, int]:
        """Rank phone candidates by digit count, then structure."""
        digits = re.sub(r"\D", "", candidate)
        has_prefix = 1 if candidate.startswith("+") else 0
        has_separators = 1 if re.search(r"[()\-.\s]", candidate) else 0
        return (len(digits), has_prefix, has_separators)

    # --------------------------------------------------------------- dates

    def _parse_date_token(self, token: str) -> date | None:
        token = token.strip().strip(".")
        m = re.fullmatch(r"([\w']+)\s+(\d{4})", token)
        if m:
            month = self.MONTHS.get(m.group(1).lower())
            if month:
                return date(int(m.group(2)), month, 1)
        if re.fullmatch(r"\d{4}", token):
            year = int(token)
            if 1950 <= year <= 2100:
                return date(year, 1, 1)
        return None

    def _parse_date_range(self, text: str) -> tuple[date | None, date | None, bool]:
        """Return ``(start, end, is_current)`` for the first date range in ``text``."""
        is_current = bool(
            re.search(
                r"\b(?:present|présent|current|now|ongoing|en cours|actuel)\b",
                text,
                re.IGNORECASE,
            )
        )
        dates: list[date] = []
        for m in self.DATE_TOKEN_RE.finditer(text):
            parsed = self._parse_date_token(m.group(1))
            if parsed is not None:
                dates.append(parsed)
        if not dates:
            return (None, None, is_current)
        if len(dates) == 1:
            return (dates[0], None, is_current)
        return (dates[0], dates[1], is_current)

    def _is_pure_date_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        without = self.DATE_TOKEN_RE.sub(" ", stripped)
        without = re.sub(
            r"\b(?:present|présent|current|now|ongoing|en cours|actuel)\b",
            " ",
            without,
            flags=re.IGNORECASE,
        )
        without = re.sub(r"[\s\-/.,:()]", "", without)
        return without == ""

    # ------------------------------------------------------------- education

    def _parse_education(self, text: str) -> tuple[Education, ...]:
        if not text.strip():
            return ()
        entries: list[Education] = []
        for block in self._split_into_blocks(text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            start, end, _ = self._parse_date_range(block)
            gpa = self._extract_gpa(block)
            location = self._find_education_location(lines)
            degree_line: str | None = None
            field_line: str | None = None
            for line in lines:
                if self._is_pure_date_line(line) or self._is_url_line(line):
                    continue
                if gpa and gpa in line:
                    continue
                if degree_line is None and detect_degree(line):
                    degree_line = line
                if field_line is None and FIELD_KEYWORDS_PATTERN.search(line):
                    field_line = line
            degree = self._normalize_degree_label(degree_line) if degree_line else None
            field = self._extract_field_phrase(field_line) if field_line else None
            institution = self._extract_institution(lines, degree_line, gpa, location)
            entries.append(
                Education(
                    institution=institution,
                    degree=degree,
                    field_of_study=field,
                    start_date=start,
                    end_date=end,
                    gpa=gpa,
                )
            )
        return tuple(entries)

    def _find_education_location(self, lines: list[str]) -> str | None:
        for line in lines:
            if self._is_pure_date_line(line) or self._is_url_line(line):
                continue
            if detect_degree(line):
                continue
            if self._is_location_line(line) or self._looks_like_place(line):
                return self._clean_location(line)
        return None

    def _extract_institution(
        self,
        lines: list[str],
        degree_line: str | None,
        gpa: str | None,
        location: str | None,
    ) -> str:
        for line in lines:
            if self._is_pure_date_line(line) or self._is_url_line(line):
                continue
            if degree_line and line == degree_line:
                continue
            if gpa and gpa in line:
                continue
            if location and line == location:
                continue
            if detect_degree(line):
                continue
            if len(line) < 3:
                continue
            return line.strip()
        return lines[0] if lines else ""

    def _normalize_degree_label(self, degree_line: str) -> str:
        detected = detect_degree(degree_line)
        if detected:
            return self.DEGREE_DISPLAY.get(detected, detected.title())
        return degree_line.strip()

    def _extract_field_phrase(self, line: str) -> str | None:
        cleaned = DEGREE_LABEL_RE.sub(" ", line)
        cleaned = re.sub(
            r"\b(?:of|in|en|studies|study|hons|honours|with|and|degree)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-—()")
        return cleaned if cleaned else None

    def _extract_gpa(self, text: str) -> str | None:
        m = self.GPA_LABEL_RE.search(text)
        if m:
            value = m.group(1)
            denom = m.group(2)
            return f"{value}/{denom}" if denom else value
        m2 = self.GPA_SCALE_RE.search(text)
        if m2:
            return m2.group(0)
        return None

    # ------------------------------------------------------------ experience

    def _parse_experience(self, text: str) -> tuple[Experience, ...]:
        if not text.strip():
            return ()
        entries: list[Experience] = []
        for block in self._split_into_blocks(text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            start, end, is_current = self._parse_date_range(block)
            _employment_type, location, remaining, technologies = self._classify_experience_lines(
                lines
            )
            if not remaining:
                continue
            company, title, description = self._split_company_title(remaining)
            if not company and not title:
                continue
            entries.append(
                Experience(
                    company=company,
                    title=title,
                    location=location,
                    start_date=start,
                    end_date=end,
                    is_current=is_current,
                    description=description,
                    technologies=tuple(technologies),
                )
            )
        return tuple(entries)

    def _classify_experience_lines(
        self, lines: list[str]
    ) -> tuple[str | None, str | None, list[str], list[str]]:
        employment_type: str | None = None
        location: str | None = None
        remaining: list[str] = []
        technologies: list[str] = []
        for raw_line in lines:
            for part in re.split(r"\s*[|]\s*|\s+-\s+", raw_line):
                part = part.strip()
                if not part:
                    continue
                if self._is_pure_date_line(part):
                    continue
                et = self._extract_employment_type(part)
                if et:
                    if employment_type is None:
                        employment_type = et
                    continue
                if self._is_url_line(part):
                    continue
                if self._is_tech_line(part):
                    technologies.append(canonical_technology(part))
                    continue
                if "," in part:
                    subparts = [s.strip() for s in part.split(",") if s.strip()]
                    if subparts and all(self._is_tech_line(s) for s in subparts):
                        technologies.extend(canonical_technology(s) for s in subparts)
                        continue
                if is_work_mode(part):
                    if location is None:
                        location = part
                    continue
                if self._is_location_line(part) or self._looks_like_place(part):
                    if location is None:
                        location = part
                    continue
                remaining.append(part)
        return employment_type, location, remaining, technologies

    @staticmethod
    def _extract_employment_type(part: str) -> str | None:
        lower = part.strip().lower()
        for label in (
            "full-time",
            "full time",
            "part-time",
            "part time",
            "contract",
            "freelance",
            "internship",
            "temporary",
            "permanent",
            "volunteer",
        ):
            if lower == label or lower.startswith(label + " "):
                return label.title()
        return None

    def _is_tech_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if len(stripped) > 30:
            return False
        if re.search(r"[.!?]\s*$", stripped):
            return False
        if _alias_key(stripped) in TECHNOLOGY_ALIASES:
            return True
        return stripped.lower() in self.TECH_WORDS

    def _split_company_title(self, lines: list[str]) -> tuple[str, str | None, str | None]:
        company: str | None = None
        title: str | None = None
        description: list[str] = []
        for index, line in enumerate(lines):
            is_role = looks_like_role(line)
            if index == 0:
                if is_role:
                    title = line
                else:
                    company = line
                continue
            if company is None and not is_role:
                company = line
            elif title is None and is_role:
                title = line
            else:
                description.append(line)
        if company is None:
            company = title or ""
            if title == company:
                title = None
        clean_company = clean_company_name(company) if company else ""
        return clean_company, title, " ".join(description) if description else None

    # -------------------------------------------------------------- projects

    def _parse_projects(self, text: str) -> tuple[Project, ...]:
        if not text.strip():
            return ()
        entries: list[Project] = []
        for block in self._split_into_blocks(text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            for sub in self._split_project_entries(lines):
                entry = self._parse_project(sub)
                if entry is not None:
                    entries.append(entry)
        return tuple(entries)

    def _split_project_entries(self, lines: list[str]) -> list[list[str]]:
        if lines and all(self._is_self_contained_project(line) for line in lines):
            return [[line] for line in lines]
        return [lines]

    @staticmethod
    def _is_self_contained_project(line: str) -> bool:
        if not line or len(line) > 140:
            return False
        if re.match(r"^(?:https?://|www\.)", line):
            return False
        has_separator = bool(re.match(r"^[^.]{2,60}\s+[—\-|]\s+\S+", line))
        has_url = bool(re.search(r"(?:https?://|www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+/", line))
        return has_separator or has_url

    def _parse_project(self, lines: list[str]) -> Project | None:
        block = "\n".join(lines)
        urls = self._extract_all_urls(block)
        start, end, _ = self._parse_date_range(block)
        technologies: list[str] = []
        description_parts: list[str] = []

        name = lines[0] if lines else ""
        parts = re.split(r"\s+[—\-|]\s+", name, maxsplit=1)
        if len(parts) > 1:
            name = parts[0].strip()
            tech_tail = parts[1].strip()
            tail_parts = [t.strip() for t in re.split(r"[,;/]", tech_tail) if t.strip()]
            if tail_parts and all(self._is_tech_line(t) for t in tail_parts):
                technologies.extend(canonical_technology(t) for t in tail_parts)
            else:
                description_parts.append(tech_tail)

        for line in lines[1:]:
            if self._is_url_line(line) or self._is_pure_date_line(line):
                continue
            lower = line.lower()
            prefixes = ("technolog", "stack", "built with", "tools")
            if any(lower.startswith(prefix) for prefix in prefixes) and ":" in lower:
                _, _, rest = line.partition(":")
                for part in re.split(r"[,;/]", rest):
                    part = canonical_technology(part.strip())
                    if part:
                        technologies.append(part)
                continue
            if self._is_tech_line(line):
                technologies.append(canonical_technology(line))
            else:
                description_parts.append(line)

        description = " ".join(description_parts).strip() if description_parts else None
        if not name:
            return None
        return Project(
            name=name,
            description=description,
            url=urls[0] if urls else None,
            technologies=tuple(technologies),
            start_date=start,
            end_date=end,
        )

    # ---------------------------------------------------------------- skills

    def _parse_skills(self, text: str) -> tuple[Skill, ...]:
        if not text.strip():
            return ()
        skills: list[Skill] = []
        seen: set[str] = set()
        items = re.split(r"[,;•|\n]", text)
        for item in items:
            item = item.strip().strip("-*").strip()
            if not item or len(item) < 2:
                continue
            name = canonical_technology(item)
            key = _alias_key(name)
            if key in seen:
                continue
            seen.add(key)
            skills.append(Skill(name=name))
        return tuple(skills)

    # ------------------------------------------------------------- languages

    CEFR_LEVELS: ClassVar[dict[str, ProficiencyLevel]] = {
        "a1": ProficiencyLevel.BASIC,
        "a2": ProficiencyLevel.BASIC,
        "b1": ProficiencyLevel.INTERMEDIATE,
        "b2": ProficiencyLevel.INTERMEDIATE,
        "c1": ProficiencyLevel.ADVANCED,
        "c2": ProficiencyLevel.FLUENT,
    }
    LEVEL_KEYWORDS: ClassVar[dict[str, ProficiencyLevel]] = {
        "native": ProficiencyLevel.NATIVE,
        "mother tongue": ProficiencyLevel.NATIVE,
        "native speaker": ProficiencyLevel.NATIVE,
        "bilingual": ProficiencyLevel.FLUENT,
        "fluent": ProficiencyLevel.FLUENT,
        "fluently": ProficiencyLevel.FLUENT,
        "professional": ProficiencyLevel.ADVANCED,
        "professional working": ProficiencyLevel.ADVANCED,
        "advanced": ProficiencyLevel.ADVANCED,
        "excellent": ProficiencyLevel.ADVANCED,
        "intermediate": ProficiencyLevel.INTERMEDIATE,
        "conversational": ProficiencyLevel.INTERMEDIATE,
        "working knowledge": ProficiencyLevel.INTERMEDIATE,
        "basic": ProficiencyLevel.BASIC,
        "elementary": ProficiencyLevel.BASIC,
        "beginner": ProficiencyLevel.BASIC,
        "notions": ProficiencyLevel.BASIC,
        "rudimentary": ProficiencyLevel.BASIC,
    }

    def _parse_languages(self, text: str) -> tuple[Language, ...]:
        if not text.strip():
            return ()
        entries: list[Language] = []
        seen: set[tuple[str, str | None]] = set()
        items = re.split(r"[,;\n]", text)
        for item in items:
            item = item.strip().strip("-*•").strip()
            if not item:
                continue
            name, proficiency = self._split_language(item)
            if not name:
                continue
            key = (name.lower(), proficiency.value if proficiency else None)
            if key in seen:
                continue
            seen.add(key)
            entries.append(Language(name=name, proficiency=proficiency))
        return tuple(entries)

    def _split_language(self, item: str) -> tuple[str, ProficiencyLevel | None]:
        text = item.strip()
        m = re.search(r"\(([^)]+)\)", text)
        level_token: str | None = None
        if m:
            level_token = m.group(1).strip()
            text = (text[: m.start()] + text[m.end() :]).strip()
        level = self._map_language_level(level_token)
        if level is None:
            words = text.split()
            for i in range(len(words) - 1, -1, -1):
                mapped = self._map_language_level(words[i]) or self._map_language_level(
                    " ".join(words[i:])
                )
                if mapped:
                    level = mapped
                    text = " ".join(words[:i]).strip()
                    break
        name = text.strip(" :,-—")
        return name, level

    def _map_language_level(self, token: str | None) -> ProficiencyLevel | None:
        if not token:
            return None
        t = token.strip().lower().strip(".,;")
        if t in self.CEFR_LEVELS:
            return self.CEFR_LEVELS[t]
        if t in self.LEVEL_KEYWORDS:
            return self.LEVEL_KEYWORDS[t]
        return None

    # --------------------------------------------------------- certifications

    def _parse_certifications(self, text: str) -> tuple[Certification, ...]:
        if not text.strip():
            return ()
        entries: list[Certification] = []
        for raw_line in text.split("\n"):
            line = raw_line.strip().strip("-*•").strip()
            if not line or len(line) < 3:
                continue
            if line.lower() in self.CERT_ISSUERS:
                if entries:
                    previous = entries[-1]
                    entries[-1] = Certification(
                        name=previous.name,
                        issuer=line,
                        date=previous.date,
                        url=previous.url,
                    )
                continue
            for item in re.split(r"[,;]", line):
                item = item.strip().strip("-*•").strip()
                if not item or len(item) < 3:
                    continue
                date = self._parse_date_range(item)[0]
                name = self.DATE_TOKEN_RE.sub(" ", item)
                name = re.sub(r"\s+", " ", name).strip(" ,;-:—()")
                if not name:
                    continue
                issuer = self._detect_cert_issuer(name)
                entries.append(Certification(name=name, issuer=issuer, date=date))
        return tuple(entries)

    def _detect_cert_issuer(self, name: str) -> str | None:
        lower = name.lower()
        for issuer in self.CERT_ISSUERS:
            if re.search(rf"\b{re.escape(issuer)}\b", lower):
                mapping = {
                    "amazon web services": "AWS",
                    "aws": "AWS",
                    "google cloud": "Google Cloud",
                    "google": "Google",
                    "comp tia": "CompTIA",
                    "comptia": "CompTIA",
                    "microsoft": "Microsoft",
                    "azure": "Microsoft Azure",
                    "oracle": "Oracle",
                    "cisco": "Cisco",
                }
                return mapping.get(issuer, issuer.title())
        return None

    # ---------------------------------------------------------------- awards

    def _parse_awards(self, text: str) -> tuple[Award, ...]:
        if not text.strip():
            return ()
        entries: list[Award] = []
        seen: set[str] = set()
        for raw_line in text.split("\n"):
            line = raw_line.strip().strip("-*•").strip()
            if not line or len(line) < 3:
                continue
            if re.search(r"\s+[—\-|]\s+", line):
                items = [line]
            else:
                items = [i.strip() for i in re.split(r"[,;]", line) if i.strip()]
            for item in items:
                date = self._parse_date_range(item)[0]
                name = re.sub(r"\b(?:19|20)\d{2}\b", " ", item)
                name = re.sub(r"\s+", " ", name).strip(" ,;-—:()")
                if not name:
                    continue
                issuer: str | None = None
                parts = re.split(r"\s+[—\-|]\s+", name, maxsplit=1)
                if len(parts) > 1:
                    name = parts[0].strip()
                    issuer = parts[1].strip().strip("()")
                    if not issuer:
                        issuer = None
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                entries.append(Award(name=name, issuer=issuer, date=date))
        return tuple(entries)

    # ---------------------------------------------------------- publications

    def _parse_publications(self, text: str) -> tuple[Publication, ...]:
        if not text.strip():
            return ()
        entries: list[Publication] = []
        for block in self._split_into_blocks(text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            if self._block_has_url_line(lines):
                entry = self._parse_publication(lines)
                if entry is not None:
                    entries.append(entry)
            elif len(lines) == 1 or all(self._is_standalone_citation(l) for l in lines):
                for line in lines:
                    entry = self._parse_publication([line])
                    if entry is not None:
                        entries.append(entry)
            else:
                entry = self._parse_publication(lines)
                if entry is not None:
                    entries.append(entry)
        return tuple(entries)

    @staticmethod
    def _block_has_url_line(lines: list[str]) -> bool:
        for line in lines:
            stripped = line.strip()
            if re.match(r"^(?:https?://|www\.)", stripped, re.IGNORECASE):
                return True
            if is_plausible_url(stripped):
                return True
        return False

    @staticmethod
    def _is_standalone_citation(line: str) -> bool:
        if len(line) > 300:
            return False
        if re.search(r"\(?\b(?:19|20)\d{2}\)?\s*[.,]", line):
            return True
        return bool(re.match(r"^[A-Z][\w'\-.]+,", line))

    def _parse_publication(self, lines: list[str]) -> Publication | None:
        urls = self._extract_all_urls("\n".join(lines))
        url = urls[0] if urls else None
        date = self._parse_date_range("\n".join(lines))[0]
        title = lines[0]
        publisher: str | None = None
        for line in lines[1:]:
            if self._is_pure_date_line(line) or self._is_url_line(line):
                continue
            lower = line.lower()
            if re.search(
                r"\b(?:journal|conference|proceedings|symposium|workshop|paper|arxiv)\b",
                lower,
            ):
                publisher = line
            else:
                title = f"{title} {line}".strip()
        if publisher is None:
            publisher = self._find_publisher_in_line(title)
            if publisher:
                title = title.replace(publisher, " ", 1)
            author = re.match(
                r"^[A-Z][\w'\-.]+,\s*[A-Z]\.?(?:\s+and\s+[A-Z][\w'\-.]+,\s*[A-Z]\.?)?",
                title,
            )
            if author:
                title = title[author.end() :].lstrip(". ")
        title = re.sub(r"\s*\(\s*(?:19|20)\d{2}\s*\)", " ", title)
        title = re.sub(r"\b(?:19|20)\d{2}\b", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" .;")
        if not title or self._is_url_line(title):
            return None
        return Publication(title=title, publisher=publisher, date=date, url=url)

    @staticmethod
    def _find_publisher_in_line(title: str) -> str | None:
        for segment in reversed(title.split(". ")):
            seg = segment.strip().strip(" .;")
            if re.search(
                r"\b(?:journal|conference|proceedings|symposium|workshop|paper|arxiv|"
                r"press|review|magazine|publications)\b",
                seg.lower(),
            ):
                return seg
        return None

    # --------------------------------------------------------------- helpers

    def _split_into_blocks(self, text: str) -> list[str]:
        """Split section text into logical blocks (blank-line separated)."""
        blocks = re.split(r"\n\s*\n", text)
        return [b.strip() for b in blocks if b.strip()]
