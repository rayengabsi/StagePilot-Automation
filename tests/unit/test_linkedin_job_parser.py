"""Unit tests for the rich LinkedIn job-posting parser.

Covers the extra fields (salary, employment type, experience level, company
size, recruiter, posted date) that turn the raw posting text into a richer
record for later matching and notification cards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.infrastructure.linkedin_mcp.job_parser import ParsedLinkedInJob, parse_linkedin_job_posting

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _parse(posting: str) -> ParsedLinkedInJob:
    return parse_linkedin_job_posting(posting, "101", now=_NOW)


def test_parses_salary_range() -> None:
    job = _parse(
        "\n".join(
            [
                "Tunis, Tunisia",
                "Backend Engineer",
                "Acme",
                "Salary: $80,000 - $110,000 per year",
                "About the job",
                "Build backend services.",
            ]
        )
    )
    assert job.salary is not None
    assert "80,000" in job.salary and "110,000" in job.salary


def test_parses_compact_k_salary() -> None:
    job = _parse(
        "\n".join(
            [
                "Paris, France",
                "Frontend Engineer",
                "Beta",
                "Compensation: €80K - €100K",
                "About the job",
                "Build interfaces.",
            ]
        )
    )
    assert job.salary is not None
    assert "80K" in job.salary and "100K" in job.salary


def test_salary_absent_when_no_mention() -> None:
    job = _parse("\n".join(["Paris", "Engineer", "Acme", "About the job", "Build things."]))
    assert job.salary is None


def test_parses_employment_type() -> None:
    job = _parse(
        "\n".join(
            [
                "Tunis, Tunisia",
                "Intern",
                "Acme",
                "Internship - 6 months",
                "About the job",
                "Work with us.",
            ]
        )
    )
    assert job.employment_type == "Internship"


def test_parses_experience_level_senior() -> None:
    job = _parse(
        "\n".join(
            [
                "Tunis, Tunisia",
                "Engineer",
                "Acme",
                "Senior Backend Engineer",
                "About the job",
                "Ship code.",
            ]
        )
    )
    assert job.experience_level == "Senior"


def test_parses_experience_entry_level_from_years_line() -> None:
    job = _parse(
        "\n".join(
            [
                "Berlin, Germany",
                "Engineer",
                "Acme",
                "Entry Level - 1+ years",
                "About the job",
                "Ship code.",
            ]
        )
    )
    assert job.experience_level == "Entry Level"


def test_parses_company_size() -> None:
    job = _parse(
        "\n".join(
            [
                "London, UK",
                "Engineer",
                "Acme",
                "11-50 employees",
                "About the job",
                "Ship code.",
            ]
        )
    )
    assert job.company_size == "11-50 employees"


def test_parses_recruiter_name() -> None:
    job = _parse(
        "\n".join(
            [
                "London",
                "Engineer",
                "Acme",
                "Recruiter",
                "Jane Doe",
                "About the job",
                "Ship code.",
            ]
        )
    )
    assert job.recruiter == "Jane Doe"


def test_parses_posted_relative_days() -> None:
    job = _parse(
        "\n".join(["London", "Engineer", "Acme", "3 days ago", "About the job", "Ship code."])
    )
    assert job.posted_at is not None
    assert job.posted_at == _NOW - timedelta(days=3)
    assert job.posted_age == "3 days ago"


def test_parses_posted_today() -> None:
    job = _parse("\n".join(["London", "Engineer", "Acme", "today", "About the job", "Ship code."]))
    assert job.posted_at == _NOW
    assert job.posted_age == "today"


def test_parses_posted_weeks() -> None:
    job = _parse(
        "\n".join(["London", "Engineer", "Acme", "2 weeks ago", "About the job", "Ship code."])
    )
    assert job.posted_at == _NOW - timedelta(weeks=2)


def test_no_posted_date_when_absent() -> None:
    job = _parse("\n".join(["London", "Engineer", "Acme", "About the job", "Ship code."]))
    assert job.posted_at is None
    assert job.posted_age is None


def test_payload_contains_rich_fields() -> None:
    job = _parse(
        "\n".join(
            [
                "London",
                "Engineer",
                "Acme",
                "Salary: 50K - 70K per year",
                "Full-time",
                "Senior",
                "2 weeks ago",
                "11-50 employees",
                "About the job",
                "Ship code.",
            ]
        )
    )
    payload = job.to_payload()
    assert payload["employment_type"] == "Full-time"
    assert payload["experience_level"] == "Senior"
    assert payload["company_size"] == "11-50 employees"
    assert payload["salary"] is not None
    assert payload["posted_at"] is not None
