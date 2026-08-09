"""Regression tests for variable-length structured sections.

CVs frequently render consecutive entries (experiences, education entries,
projects, languages) without a blank line between them. The normalizer must
preserve every entry generically (0, 1, or many) and never hardcode counts.
All fixtures below are synthetic and intentionally contain no real personal
data.
"""

from __future__ import annotations

from datetime import date

from app.domain.master_profile.enums import ProficiencyLevel
from app.services.profile_normalizer import ProfileNormalizer


def _normalize(text: str) -> object:
    return ProfileNormalizer().normalize(text)


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------


def test_experience_single_entry() -> None:
    p = _normalize(
        """Experience
Backend Engineer - Riviera Tech
Jan. 2021 - Dec. 2022
Designed internal APIs.
"""
    )
    assert len(p.experience) == 1
    exp = p.experience[0]
    assert exp.title == "Backend Engineer"
    assert exp.company == "Riviera Tech"
    assert exp.start_date == date(2021, 1, 1)
    assert exp.end_date == date(2022, 12, 1)


def test_experience_multiple_entries_no_blank_lines() -> None:
    p = _normalize(
        """Experience
Software Engineering Intern Jul. 2026 - Present
Acme Software
Built microservices.
Designed dashboards.
Software Engineering Intern Jul. 2025 - Aug. 2025
Bees Inc
Built REST APIs.
"""
    )
    assert len(p.experience) == 2
    first, second = p.experience
    assert first.company == "Acme Software"
    assert first.title == "Software Engineering Intern"
    assert first.start_date == date(2026, 7, 1)
    assert first.is_current is True
    assert "Designed dashboards." in (first.description or "")
    assert second.company == "Bees Inc"
    assert second.start_date == date(2025, 7, 1)
    assert second.end_date == date(2025, 8, 1)
    assert first.description is not None and "Acme Software" not in first.description


def test_experience_dates_on_separate_lines() -> None:
    p = _normalize(
        """Experience
Senior Developer | Foxtrot Ltd
January 2020 - Present
- Led platform team.

QA Engineer | Foxtrot Ltd
2017 - 2019
- Wrote test suites.
"""
    )
    assert len(p.experience) == 2
    assert p.experience[0].company == "Foxtrot Ltd"
    assert p.experience[0].title == "Senior Developer"
    assert p.experience[0].is_current is True
    assert p.experience[1].company == "Foxtrot Ltd"
    assert p.experience[1].is_current is False


def test_experience_zero_entries() -> None:
    p = _normalize("Jane Smith\njane@example.com\nSkills\nPython\n")
    assert p.experience == ()
    p = _normalize("Jane Smith\nExperience\n")
    assert p.experience == ()


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


def test_education_multiple_entries_back_to_back() -> None:
    p = _normalize(
        """Education
Oak Institute - Private School of Engineering Metropolis North
Engineering Degree in Computer Engineering Sep. 2020 - Jun. 2024
Elm City High School
High School Diploma Sep. 2016 - Jun. 2020
"""
    )
    assert len(p.education) == 2
    first, second = p.education
    assert first.institution.startswith("Oak Institute")
    assert first.degree == "Engineering Degree"
    assert first.field_of_study == "Computer Engineering"
    assert first.start_date == date(2020, 9, 1)
    assert second.institution.startswith("Elm City High School")
    assert second.start_date == date(2016, 9, 1)


def test_education_single_entry() -> None:
    p = _normalize(
        """Education
State University
B.S. in Computer Science
2014 - 2018
"""
    )
    assert len(p.education) == 1


def test_education_zero_entries() -> None:
    p = _normalize("Jane Smith\nEmail: jane@example.com\n")
    assert p.education == ()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def test_projects_single_entry() -> None:
    p = _normalize(
        """Projects
Invoice Tool - Python, Django
https://example.com/invoice
Scans PDFs and exports totals.
"""
    )
    assert len(p.projects) == 1
    proj = p.projects[0]
    assert proj.name == "Invoice Tool"
    assert "Python" in proj.technologies


def test_projects_multiple_entries_back_to_back() -> None:
    p = _normalize(
        """Projects
TradeSim AI - FastAPI, React
Built an AI trading simulator.
Streamed quotes over WebSockets.
TripPal - FastAPI, React Native, Firebase
Built a trip planner app.
Integrated booking APIs.
"""
    )
    assert len(p.projects) == 2
    first, second = p.projects
    assert first.name == "TradeSim AI"
    assert second.name == "TripPal"
    assert "Firebase" in second.technologies


def test_projects_zero_entries() -> None:
    p = _normalize("Jane Smith\nTelephone: +216 71 000 000\n")
    assert p.projects == ()


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


def test_languages_single_entry() -> None:
    p = _normalize("Languages\nGerman (B2)")
    assert len(p.languages) == 1
    assert p.languages[0].name == "German"


def test_languages_pipe_colon_joined() -> None:
    p = _normalize("Languages\nArabic: Native | French: B2 | English: B2")
    langs = {l.name: l.proficiency for l in p.languages}
    assert langs == {
        "Arabic": ProficiencyLevel.NATIVE,
        "French": ProficiencyLevel.INTERMEDIATE,
        "English": ProficiencyLevel.INTERMEDIATE,
    }


def test_languages_multiple_on_separate_lines() -> None:
    p = _normalize(
        """Languages
German (C1)
Italian (fluent)
"""
    )
    assert len(p.languages) == 2


def test_languages_zero_entries() -> None:
    p = _normalize("Jane Smith\nEmail: jane@example.com\n")
    assert p.languages == ()


# ---------------------------------------------------------------------------
# Structure / ordering / absent sections
# ---------------------------------------------------------------------------


def test_sections_in_different_order() -> None:
    p = _normalize(
        """Jane Smith
janed@example.com

Skills
Python, Java

Education
City College
BA
2018 - 2022

Experience
Software Engineer | WebWorks Inc
2019 - 2023
Built frontend tools.

Languages
French (B2), Arabic (Native)
"""
    )
    assert len(p.experience) == 1
    assert len(p.education) == 1
    assert len(p.skills) >= 2
    assert len(p.languages) == 2


def test_absent_optional_sections() -> None:
    p = _normalize(
        """Jane Smith
Jane Smith

Education
City College
BA
2018 - 2022
"""
    )
    assert len(p.education) == 1
    assert p.experience == ()
    assert p.projects == ()
    assert p.languages == ()
    assert p.certifications == ()
    assert p.awards == ()
    assert p.publications == ()


def test_three_experience_entries_preserved() -> None:
    p = _normalize(
        """Experience
Engineer A - Jan 2020 - Present
Company A

Engineer B - Feb 2019 - Dec 2019
Company B
Engineer C - Mar 2018 - Dec 2018
Company C
"""
    )
    assert len(p.experience) == 3


def test_multi_line_description_preserved() -> None:
    p = _normalize(
        """Experience
DevOps Engineer - Aug 2022 - Present
OpsWorks
Built the CI pipeline.
Cut deploy time in half.

Education
North University
MSc in Computer Science
2020 - 2022
"""
    )
    exp = p.experience[0]
    assert exp.description == "Built the CI pipeline. Cut deploy time in half."


def test_repeated_entries_same_section_no_blank_lines() -> None:
    p = _normalize(
        """Certifications
AWS Certified Solutions Architect (2021)
Google Cloud Professional Data Engineer (2022)
"""
    )
    assert len(p.certifications) == 2
