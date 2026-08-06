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
        }


def parse_linkedin_job_posting(text: str, job_id: str) -> ParsedLinkedInJob:
    """Parse a raw LinkedIn job posting text block into structured fields."""
    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    lines = _clean_lines(text)

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

    return ParsedLinkedInJob(
        url=url,
        job_id=job_id,
        title=_clean(title),
        company=_clean(company),
        location=_location(location),
        description=_join(description_parts),
        requirements=_join(requirements_parts),
        work_mode=_detect_work_mode(lines),
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
