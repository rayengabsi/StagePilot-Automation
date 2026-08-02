from __future__ import annotations

from app.services.profile_normalizer import ProfileNormalizer


def test_normalizer_extracts_email_and_phone() -> None:
    text = """John Doe
    john@example.com
    +216 99 123 456
    https://github.com/johndoe

Education
University of Tunis
Master in Computer Science
2019 2023

Skills
Python, Java, SQL, Docker
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert profile.personal_info.full_name == "John Doe"
    assert profile.personal_info.email == "john@example.com"
    assert profile.personal_info.phone is not None


def test_normalizer_extracts_education() -> None:
    text = """Jane Smith

Education
University of Tunis
Bachelor in Computer Science
2018 2022

National Institute
Master in Data Science
2022 2024
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.education) >= 1
    assert profile.education[0].institution == "University of Tunis"


def test_normalizer_extracts_skills() -> None:
    text = """Skills
Python, Java, JavaScript, React, Docker, Kubernetes
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.skills) >= 3


def test_normalizer_handles_empty_text() -> None:
    n = ProfileNormalizer()
    profile = n.normalize("")
    assert profile.personal_info.full_name == ""


def test_normalizer_extracts_experience() -> None:
    text = """Experience
Tech Corp
Software Engineer Intern
June 2023 August 2023
Worked on backend APIs using Python.
Python
Django
PostgreSQL
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.experience) >= 1
    assert profile.experience[0].company == "Tech Corp"


def test_normalizer_extracts_projects() -> None:
    text = """Projects
E-commerce Platform
Built a full-stack e-commerce site.
Python
Django
React
https://github.com/user/ecommerce
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.projects) >= 1
    assert profile.projects[0].name == "E-commerce Platform"


def test_normalizer_extracts_languages() -> None:
    text = """Languages
English (fluent), French (native), Arabic (native)
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.languages) >= 2


def test_normalizer_extracts_certifications() -> None:
    text = """Certifications
AWS Certified Solutions Architect, Google Cloud Professional
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.certifications) >= 2


def test_normalizer_splits_sections_correctly() -> None:
    text = """John Doe

Education
University A
2020 2024

Skills
Python, Java

Experience
Company B
2023 2024
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert len(profile.education) >= 1
    assert len(profile.skills) >= 1
    assert len(profile.experience) >= 1


def _ats_resume(
    *,
    name: str,
    phone: str,
    years: list[str],
    phone_first: bool = False,
) -> str:
    """Build a generic ATS-style resume with contact info and dated roles.

    The years (employment/education dates) are placed before the contact block
    unless ``phone_first`` is set, mirroring ATS extractions where dates precede
    the contact line.
    """
    header = f"{name}\nFull-Stack Developer\n"
    contact = f"Email: {name.lower().replace(' ', '.')}@example.com\nPhone: {phone}\n"
    experience = "\n".join(
        [
            "EXPERIENCE",
            "Senior Software Engineer | Acme Corp",
            f"{years[0]} - {years[1]}",
            "- Led migration to Kubernetes.",
        ]
    )
    education = "\n".join(
        [
            "EDUCATION",
            "State University",
            "B.S. Computer Science",
            f"{years[2]} - {years[3]}",
        ]
    )
    if phone_first:
        return "\n".join([header, contact, experience, education])
    return "\n".join([header, experience, education, contact])


def test_normalizer_prefers_phone_over_isolated_years() -> None:
    """ATS resumes with dated roles and a contact phone must extract the phone."""
    resume = _ats_resume(
        name="Alex Johnson",
        phone="+216 53 852 323",
        years=["2018", "2025", "2014", "2018"],
    )
    n = ProfileNormalizer()
    profile = n.normalize(resume)
    assert profile.personal_info.phone == "+216 53 852 323"


def test_normalizer_prefers_phone_when_years_precede_contact() -> None:
    """Years appearing before the contact block must not shadow the phone."""
    resume = _ats_resume(
        name="Samira Trabelsi",
        phone="+1 (555) 123-4567",
        years=["2020", "2025", "2016", "2020"],
    )
    n = ProfileNormalizer()
    profile = n.normalize(resume)
    assert profile.personal_info.phone == "+1 (555) 123-4567"


def test_normalizer_rejects_isolated_years_as_phone() -> None:
    """A resume containing only years must not yield a phone number."""
    text = """Jane Smith
Backend Engineer

EXPERIENCE
Senior Engineer | Example Ltd
2020 - 2025
- Built internal tooling.

EDUCATION
Example University
B.S. Computer Science
2014 - 2018
"""
    n = ProfileNormalizer()
    profile = n.normalize(text)
    assert profile.personal_info.phone is None


def test_extract_phone_rejects_isolated_year() -> None:
    from app.services.profile_normalizer import ProfileNormalizer

    n = ProfileNormalizer()
    assert n._extract_phone("Started in 2025 as a team lead.") is None
    assert n._extract_phone("2025\n+216 53 852 323") == "+216 53 852 323"


def test_is_isolated_year() -> None:
    from app.services.profile_normalizer import ProfileNormalizer

    assert ProfileNormalizer._is_isolated_year("2025") is True
    assert ProfileNormalizer._is_isolated_year("1995") is True
    assert ProfileNormalizer._is_isolated_year("+216 53 852 323") is False
    assert ProfileNormalizer._is_isolated_year("55 1234") is False
