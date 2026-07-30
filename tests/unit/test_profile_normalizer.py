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
