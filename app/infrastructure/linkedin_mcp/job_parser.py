"""Best-effort parser for LinkedIn job-posting text.

The real LinkedIn MCP server's ``get_job_details`` returns ``{url, sections:
{"job_posting": <raw innerText>}}`` — freeform text, not structured JSON. This
module converts that text into the fields the matching engine expects (title,
company, location, description, requirements). It is deliberately best-effort
and deterministic: unknown or noisy fields fall back to meaningful defaults
rather than rejecting the job. The canonical job URL/ID always come from the
known ``https://www.linkedin.com/jobs/view/{job_id}/`` shape, never from text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.shared.time import utc_now

_DESCRIPTION_HEADERS = (
    "about the job",
    "about this job",
    "job description",
    "description",
    "job",
    "what you'll do",
    "role summary",
    "role overview",
    "responsibilities",
    "the role",
    "overview",
    "summary",
    "duties",
    "key responsibilities",
)

_REQUIREMENTS_HEADERS = (
    "requirements",
    "minimum qualifications",
    "basic qualifications",
    "preferred qualifications",
    "qualifications",
    "what you'll bring",
    "must have",
    "nice to have",
    "experience required",
    "about you",
)

_REMOTE_TOKENS = ("remote", "telework", "hybrid", "on-site", "on site", "flexible")
_KNOWN_COUNTRIES = (
    "germany",
    "france",
    "spain",
    "italy",
    "portugal",
    "netherlands",
    "belgium",
    "uae",
    "united arab emirates",
    "united states",
    "usa",
    "tunisia",
    "morocco",
    "egypt",
    "united kingdom",
    "uk",
    "canada",
    "poland",
    "sweden",
    "switzerland",
)

_TITLE_STOP = (
    "about the job",
    "about this job",
    "job description",
    "requirements",
    "qualifications",
    "responsibilities",
    "full-time",
    "part-time",
    "internship",
    "contract",
    "temporary",
    "on-site",
    "remote",
    "hybrid",
    "location",
    "salary",
    "title",
    "job title",
    "compensation",
)


@dataclass(frozen=True, slots=True)
class ParsedLinkedInJob:
    """Structured fields derived from one LinkedIn job-posting text block."""

    url: str
    job_id: str
    title: str | None
    company: str | None
    location: str | None
    description: str | None
    requirements: str | None
    work_mode: str | None
    salary: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    company_size: str | None = None
    recruiter: str | None = None
    posted_at: datetime | None = None
    posted_age: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation for ``raw_payload``."""
        return {
            "url": self.url,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "requirements": self.requirements,
            "work_mode": self.work_mode,
            "salary": self.salary,
            "employment_type": self.employment_type,
            "experience_level": self.experience_level,
            "company_size": self.company_size,
            "recruiter": self.recruiter,
            "posted_age": self.posted_age,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


def parse_linkedin_job_posting(
    text: str, job_id: str, now: datetime | None = None
) -> ParsedLinkedInJob:
    """Parse a raw LinkedIn job posting text block into structured fields."""
    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    lines = _clean_lines(text)
    reference = now or utc_now()

    location: str | None = None
    title: str | None = None
    company: str | None = None
    description_parts: list[str] = []
    requirements_parts: list[str] = []

    mode = "header"
    for line in lines:
        lowered = line.lower()
        if _is_requirements_header(lowered):
            mode = "requirements"
            continue
        if _is_description_header(lowered):
            mode = "description"
            continue

        if mode == "description":
            description_parts.append(line)
            continue
        if mode == "requirements":
            requirements_parts.append(line)
            continue

        # header zone: collect location, then title, then company
        if location is None and _looks_like_location(line):
            location = line
            continue
        if title is None and _looks_like_title(line):
            title = line
            continue
        if company is None and _looks_like_company(line):
            company = line

    posted_at, posted_age = _parse_posted(lines, reference)
    return ParsedLinkedInJob(
        url=url,
        job_id=job_id,
        title=_clean(title),
        company=_clean(company),
        location=_location(location),
        description=_join(description_parts),
        requirements=_join(requirements_parts),
        work_mode=_detect_work_mode(lines),
        salary=_parse_salary(lines),
        employment_type=_parse_employment_type(lines),
        experience_level=_parse_experience_level(lines),
        company_size=_parse_company_size(lines),
        recruiter=_parse_recruiter(lines),
        posted_at=posted_at,
        posted_age=posted_age,
    )


def _clean_lines(text: str) -> list[str]:
    """Return non-empty, stripped lines that are not pure separators."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[=_\-\*\.─\s]+", line):
            continue
        out.append(line)
    return out


def _join(parts: list[str]) -> str | None:
    text = "\n".join(parts).strip()
    return text or None


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split())


def _is_description_header(lowered: str) -> bool:
    return _any_equals(lowered, _DESCRIPTION_HEADERS)


def _is_requirements_header(lowered: str) -> bool:
    return _any_equals(lowered, _REQUIREMENTS_HEADERS)


def _any_equals(lowered: str, markers: tuple[str, ...]) -> bool:
    stripped = lowered.rstrip(":").strip()
    return stripped in markers or any(m in stripped for m in markers if m)


def _looks_like_location(line: str) -> bool:
    lowered = line.lower()
    if any(token in lowered for token in _REMOTE_TOKENS):
        return True
    if len(line) > 60:
        return False
    if any(country in lowered for country in _KNOWN_COUNTRIES):
        return True
    return "," in line and len(line) <= 45


def _location(value: str | None) -> str | None:
    if not value:
        return "Remote"
    return _clean(value)


def _looks_like_title(line: str) -> bool:
    lowered = line.lower()
    if len(line) < 3 or len(line) > 120:
        return False
    if _any_equals(lowered, _TITLE_STOP):
        return False
    return lowered not in _DESCRIPTION_HEADERS and lowered not in _REQUIREMENTS_HEADERS


def _looks_like_company(line: str) -> bool:
    lowered = line.lower()
    if len(line) < 3 or len(line) > 80:
        return False
    if _looks_like_location(line):
        return False
    if _any_equals(lowered, _TITLE_STOP):
        return False
    return lowered not in _DESCRIPTION_HEADERS and lowered not in _REQUIREMENTS_HEADERS


def _detect_work_mode(lines: list[str]) -> str | None:
    for line in lines:
        lowered = line.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        if "on-site" in lowered or "on site" in lowered:
            return "on_site"
    return None


_SALARY_RE = re.compile(
    r"(?:[$€£₹]\s*)?"
    r"(?P<lo>\d[\d,\.]*\s?[kKM]?)"
    r"\s*(?:to|-|\u2013|\u2014)\s*"
    r"(?:[$€£₹]\s*)?"
    r"(?P<hi>\d[\d,\.]*\s?[kKM]?)",
    re.IGNORECASE,
)

_SALARY_WORD_RE = re.compile(
    r"(salary|compensation|remuneration|annual|per year|per hour)",
    re.IGNORECASE,
)

_EMPLOYMENT_TYPE_TOKENS = (
    ("full-time", "Full-time"),
    ("full time", "Full-time"),
    ("part-time", "Part-time"),
    ("part time", "Part-time"),
    ("contract", "Contract"),
    ("temporary", "Temporary"),
    ("internship", "Internship"),
    ("intern", "Internship"),
)

_EXPERIENCE_TOKENS = (
    ("executive", "Executive"),
    ("director", "Director"),
    ("lead", "Lead"),
    ("principal", "Principal"),
    ("senior", "Senior"),
    ("mid-senior", "Mid-Senior"),
    ("mid senior", "Mid-Senior"),
    ("associate", "Associate"),
    ("entry level", "Entry Level"),
    ("entry-level", "Entry Level"),
    ("intern", "Intern"),
    ("student", "Intern"),
    ("junior", "Entry Level"),
)

_COMPANY_SIZE_RE = re.compile(
    r"^\s*(?P<size>[\d\-,\.\s]+(?:employees|staff|people))\s*$",
    re.IGNORECASE,
)


def _parse_salary(lines: list[str]) -> str | None:
    """Return the first recognised salary line (range or single figure)."""
    for line in lines:
        if not _SALARY_WORD_RE.search(line):
            continue
        if _SALARY_RE.search(line):
            return _clean(line)
    return None


def _parse_employment_type(lines: list[str]) -> str | None:
    """Return a normalised employment type if one is advertised."""
    for line in lines:
        lowered = line.lower()
        for token, label in _EMPLOYMENT_TYPE_TOKENS:
            if token in lowered:
                return label
    return None


def _parse_experience_level(lines: list[str]) -> str | None:
    """Return a seniority label or a seniority string for years required."""
    for line in lines:
        lowered = line.lower()
        for token, label in _EXPERIENCE_TOKENS:
            if token in lowered:
                return label
    return None


def _parse_company_size(lines: list[str]) -> str | None:
    """Return the advertised company employee range, if present."""
    for line in lines:
        if _COMPANY_SIZE_RE.match(line):
            return _clean(line)
    return None


def _parse_recruiter(lines: list[str]) -> str | None:
    """Return the recruiter/contact name if a recruiter block is present."""
    for index, line in enumerate(lines):
        if "recruiter" not in line.lower():
            continue
        for candidate in (line, lines[index + 1]) if index + 1 < len(lines) else (line,):
            stripped = _clean(candidate)
            if not stripped or stripped.lower() == "recruiter":
                continue
            return stripped
    return None


def _parse_posted(lines: list[str], now: datetime) -> tuple[datetime | None, str | None]:
    """Turn a relative posting-age text into an ISO date + the raw age text."""
    for line in lines:
        age = _match_age(line)
        if age is None:
            continue
        return now - age, _clean(line)
    return None, None


def _match_age(line: str) -> timedelta | None:
    """Convert a relative date phrase to a timedelta, or None."""
    lowered = line.lower().strip()
    if lowered in {"today", "just now", "recently", "posted today"}:
        return timedelta(0)
    if lowered.startswith("just posted") or lowered == "new":
        return timedelta(0)

    match = re.search(r"(\d+)\s*(hour|hr|h|day|d|week|w|month|mo|year|yr|y)\w*", lowered)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in {"hour", "hr", "h"}:
        return timedelta(hours=amount)
    if unit in {"day", "d"}:
        return timedelta(days=amount)
    if unit in {"week", "w"}:
        return timedelta(weeks=amount)
    if unit in {"month", "mo"}:
        return timedelta(days=amount * 30)
    if unit in {"year", "yr", "y"}:
        return timedelta(days=amount * 365)
    return None
