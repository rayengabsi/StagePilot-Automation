from __future__ import annotations

from datetime import date

from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.enums import ProficiencyLevel
from app.services.profile_normalizer import ProfileNormalizer
from app.utils.normalization import canonical_technology, normalize_url
from app.utils.text_cleaning import clean as clean_text


def _normalize(text: str) -> MasterProfile:
    return ProfileNormalizer().normalize(text)


# ---------------------------------------------------------------------------
# Contact information
# ---------------------------------------------------------------------------


def test_extracts_full_header_contact_block() -> None:
    text = """Jane Smith
San Francisco, CA
Email: jane.smith@example.com
Phone: +1 (555) 123-4567
Nationality: American
"""
    p = _normalize(text)
    assert p.personal_info.full_name == "Jane Smith"
    assert p.personal_info.email == "jane.smith@example.com"
    assert p.personal_info.phone == "+1 (555) 123-4567"
    assert p.personal_info.location == "San Francisco, CA"
    assert p.personal_info.nationality == "American"


def test_extracts_linkedin_labeled_and_bare() -> None:
    cases = [
        (
            "LinkedIn: https://www.linkedin.com/in/janesmith",
            "https://www.linkedin.com/in/janesmith",
        ),
        ("linkedin.com/in/janesmith", "https://linkedin.com/in/janesmith"),
        ("LinkedIn: linkedin.com/in/janesmith", "https://linkedin.com/in/janesmith"),
        ("https://linkedin.com/in/janesmith/", "https://linkedin.com/in/janesmith"),
    ]
    for value, expected in cases:
        p = _normalize(f"Jane Smith\n{value}")
        assert p.personal_info.linkedin_url == expected, value


def test_extracts_github_labeled_and_bare() -> None:
    cases = [
        ("GitHub: https://github.com/janesmith", "https://github.com/janesmith"),
        ("github.com/janesmith", "https://github.com/janesmith"),
        ("https://www.github.com/janesmith/", "https://www.github.com/janesmith"),
    ]
    for value, expected in cases:
        p = _normalize(f"Jane Smith\n{value}")
        assert p.personal_info.github_url == expected, value


def test_extracts_portfolio_from_label_and_bare_url() -> None:
    labeled = _normalize("Jane Smith\nPortfolio: https://janesmith.dev")
    assert labeled.personal_info.portfolio_url == "https://janesmith.dev"

    bare = _normalize("Jane Smith\nwww.janesmith.dev")
    assert bare.personal_info.portfolio_url == "https://www.janesmith.dev"


def test_separates_linkedin_github_and_portfolio() -> None:
    p = _normalize(
        """John Carter
john.carter@example.com
linkedin.com/in/johncarter
https://github.com/johncarter
https://johncarter.dev
"""
    )
    assert p.personal_info.linkedin_url == "https://linkedin.com/in/johncarter"
    assert p.personal_info.github_url == "https://github.com/johncarter"
    assert p.personal_info.portfolio_url == "https://johncarter.dev"


def test_extracts_location_from_label_and_plain_line() -> None:
    labeled = _normalize("Jane Smith\nLocation: Tunis, Tunisia")
    assert labeled.personal_info.location == "Tunis, Tunisia"

    plain = _normalize("Jane Smith\nSeattle, WA")
    assert plain.personal_info.location == "Seattle, WA"


def test_name_not_polluted_by_role_line() -> None:
    p = _normalize("Jane Smith\nSenior Full-Stack Engineer\njane@example.com")
    assert p.personal_info.full_name == "Jane Smith"


def test_normalize_url_adds_scheme_and_strips_trailing_slash() -> None:
    assert normalize_url("www.example.com/") == "https://www.example.com"
    assert normalize_url("EXAMPLE.COM") == "https://example.com"
    assert normalize_url("https://GitHub.com/foo/") == "https://github.com/foo"
    assert normalize_url("") is None


def test_canonical_technology_aliases() -> None:
    assert canonical_technology("nodejs") == "Node.js"
    assert canonical_technology("postgres") == "PostgreSQL"
    assert canonical_technology("aws") == "AWS"
    assert canonical_technology("golang") == "Go"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_extracts_summary_from_summary_section() -> None:
    p = _normalize(
        """Jane Smith
jane@example.com

Summary
Senior backend engineer with 8 years of experience building distributed systems.
"""
    )
    assert (
        p.personal_info.summary
        == "Senior backend engineer with 8 years of experience building distributed systems."
    )


def test_extracts_summary_from_header_region_when_no_section() -> None:
    p = _normalize(
        """Alice Johnson
Software Engineer with 10 years of experience across fintech and e-commerce.
Passionate about distributed systems and clean architecture.
alice.johnson@example.com
+44 20 7946 0958
London, UK
"""
    )
    assert "Software Engineer with 10 years" in (p.personal_info.summary or "")


def test_summary_does_not_include_contact_lines() -> None:
    p = _normalize(
        """John Carter
Software Engineer focused on backend systems.
john.carter@example.com
+1 (206) 555-0199
linkedin.com/in/johncarter
https://github.com/johncarter
"""
    )
    summary = p.personal_info.summary
    assert summary == "Software Engineer focused on backend systems."
    assert "linkedin" not in (summary or "").lower()
    assert "github" not in (summary or "").lower()


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------


def test_experience_company_title_location_and_dates() -> None:
    p = _normalize(
        """Experience
Senior Software Engineer | Acme Corp | San Francisco, CA
March 2020 - Present
- Led migration to Kubernetes.
"""
    )
    assert len(p.experience) == 1
    exp = p.experience[0]
    assert exp.company == "Acme Corp"
    assert exp.title == "Senior Software Engineer"
    assert exp.location == "San Francisco, CA"
    assert exp.start_date == date(2020, 3, 1)
    assert exp.end_date is None
    assert exp.is_current is True


def test_experience_employment_type_and_work_mode() -> None:
    p = _normalize(
        """Experience
Backend Developer | Globex | Remote
Full-Time | Remote
2017 - 2020
Java
"""
    )
    exp = p.experience[0]
    assert exp.company == "Globex"
    assert exp.location == "Remote"
    assert exp.is_current is False


def test_experience_multiple_entries_split_by_blank_lines() -> None:
    p = _normalize(
        """Experience
Senior Software Engineer | Acme Corp
2020 - Present
Python

Backend Developer | Globex
2017 - 2020
Java
"""
    )
    assert len(p.experience) == 2
    assert p.experience[0].company == "Acme Corp"
    assert p.experience[1].company == "Globex"


def test_experience_technologies_from_own_lines() -> None:
    p = _normalize(
        """Experience
Tech Corp
Software Engineer Intern
June 2023 August 2023
Worked on backend APIs.
Python
Django
PostgreSQL
"""
    )
    assert len(p.experience) >= 1
    exp = p.experience[0]
    assert exp.company == "Tech Corp"
    assert set(exp.technologies) == {"Python", "Django", "PostgreSQL"}


def test_experience_technologies_comma_separated_on_one_line() -> None:
    p = _normalize(
        """Experience
Backend Developer - Globex
2017 - 2020
Java, Spring Boot
"""
    )
    exp = p.experience[0]
    assert exp.company == "Globex"
    assert exp.title == "Backend Developer"
    assert set(exp.technologies) == {"Java", "Spring Boot"}


def test_experience_title_first_then_company() -> None:
    p = _normalize(
        """Experience
Software Engineer
Acme Corp
2020 - 2022
"""
    )
    exp = p.experience[0]
    assert exp.company == "Acme Corp"
    assert exp.title == "Software Engineer"


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


def test_education_abbreviated_degrees() -> None:
    cases = [
        ("B.S. in Computer Science", "Bachelor of Science", "Computer Science"),
        ("BSc Computer Science", "Bachelor of Science", "Computer Science"),
        ("M.Sc. in Data Science", "Master of Science", "Data Science"),
        ("MBA", "MBA", None),
    ]
    for line, degree, field in cases:
        p = _normalize(f"""Education
State University
{line}
2014 - 2018
""")
        assert len(p.education) == 1, line
        edu = p.education[0]
        assert edu.degree == degree, line
        assert edu.field_of_study == field, line


def test_education_full_degree_names() -> None:
    p = _normalize(
        """Education
National Institute
Master of Science in Data Science
2022 - 2024
"""
    )
    edu = p.education[0]
    assert edu.institution == "National Institute"
    assert edu.degree == "Master of Science"
    assert edu.field_of_study == "Data Science"


def test_education_multiple_entries_and_gpa() -> None:
    p = _normalize(
        """Education
State University
B.S. in Computer Science
GPA: 3.8/4.0
2014 - 2018

National Institute
MSc in Data Science
2022 - 2024
"""
    )
    assert len(p.education) == 2
    assert p.education[0].institution == "State University"
    assert p.education[0].gpa == "3.8/4.0"
    assert p.education[1].institution == "National Institute"


def test_education_dates() -> None:
    p = _normalize(
        """Education
University A
Bachelor
September 2015 - June 2019
"""
    )
    edu = p.education[0]
    assert edu.start_date == date(2015, 9, 1)
    assert edu.end_date == date(2019, 6, 1)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def test_project_name_tech_and_url() -> None:
    p = _normalize(
        """Projects
E-commerce Platform | Python, Django, React
https://github.com/user/ecommerce
Full-stack storefront with payments.
"""
    )
    assert len(p.projects) >= 1
    proj = p.projects[0]
    assert proj.name == "E-commerce Platform"
    assert proj.url == "https://github.com/user/ecommerce"
    assert set(proj.technologies) == {"Python", "Django", "React"}


def test_project_built_with_technologies_line() -> None:
    p = _normalize(
        """Projects
Task Manager API
Built with: Flask, PostgreSQL, Docker
https://github.com/user/tasks
REST API with JWT auth.
"""
    )
    proj = p.projects[0]
    assert proj.name == "Task Manager API"
    assert set(proj.technologies) == {"Flask", "PostgreSQL", "Docker"}
    assert proj.url == "https://github.com/user/tasks"


def test_multiple_projects_split_by_blank_lines() -> None:
    p = _normalize(
        """Projects
Project Alpha | Python
https://github.com/user/alpha

Project Beta | Go
https://github.com/user/beta
"""
    )
    assert len(p.projects) == 2
    assert p.projects[0].name == "Project Alpha"
    assert p.projects[1].name == "Project Beta"


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


def test_language_cefr_levels() -> None:
    p = _normalize("Languages\nEnglish (C1), French (C2), Spanish (B1)")
    levels = {l.name: l.proficiency for l in p.languages}
    assert levels["English"] == ProficiencyLevel.ADVANCED
    assert levels["French"] == ProficiencyLevel.FLUENT
    assert levels["Spanish"] == ProficiencyLevel.INTERMEDIATE


def test_language_keyword_levels() -> None:
    p = _normalize(
        "Languages\nEnglish (native), French (fluent), Arabic (intermediate), German (basic)"
    )
    levels = {l.name: l.proficiency for l in p.languages}
    assert levels["English"] == ProficiencyLevel.NATIVE
    assert levels["French"] == ProficiencyLevel.FLUENT
    assert levels["Arabic"] == ProficiencyLevel.INTERMEDIATE
    assert levels["German"] == ProficiencyLevel.BASIC


def test_language_duplicates_removed() -> None:
    p = _normalize("Languages\nEnglish (Native), English (Native), French (C1), French (Advanced)")
    assert len(p.languages) == 2


# ---------------------------------------------------------------------------
# Certifications / Awards / Publications
# ---------------------------------------------------------------------------


def test_certification_issuer_and_date() -> None:
    p = _normalize(
        """Certifications
AWS Certified Solutions Architect (2021)
Google Cloud Professional Data Engineer
Cisco CCNA
"""
    )
    certs = {c.name: c for c in p.certifications}
    assert "AWS Certified Solutions Architect" in certs
    assert certs["AWS Certified Solutions Architect"].issuer == "AWS"
    assert certs["AWS Certified Solutions Architect"].date == date(2021, 1, 1)
    assert "Google Cloud Professional Data Engineer" in certs
    assert certs["Google Cloud Professional Data Engineer"].issuer == "Google Cloud"
    assert "Cisco CCNA" in certs


def test_award_name_issuer_and_date() -> None:
    p = _normalize(
        """Awards
Dean's List - 2019
First Place, National Hackathon 2020 - ACM
"""
    )
    awards = {a.name: a for a in p.awards}
    assert "Dean's List" in awards
    assert awards["Dean's List"].date == date(2019, 1, 1)
    assert "First Place, National Hackathon" in awards
    assert awards["First Place, National Hackathon"].issuer == "ACM"
    assert awards["First Place, National Hackathon"].date == date(2020, 1, 1)


def test_publication_citation_format() -> None:
    p = _normalize(
        """Publications
Smith, J. and Doe, A. (2021). Distributed Systems for Fun. ACM Journal.
https://doi.org/10.1000/xyz
"""
    )
    assert len(p.publications) >= 1
    pub = p.publications[0]
    assert pub.title == "Distributed Systems for Fun"
    assert pub.publisher == "ACM Journal"
    assert pub.date == date(2021, 1, 1)
    assert pub.url == "https://doi.org/10.1000/xyz"


def test_publication_url_only_block_skipped() -> None:
    p = _normalize(
        """Publications
Chen, X. (2020). Edge Caching. IEEE Conference on Cloud Computing.

https://doi.org/10.1000/xyz
"""
    )
    titles = [pub.title for pub in p.publications]
    assert "Edge Caching" in titles
    assert not any("doi.org" in t for t in titles)


# ---------------------------------------------------------------------------
# French-language resumes
# ---------------------------------------------------------------------------


def test_french_section_headers_and_months() -> None:
    p = _normalize(
        """Marie Dupont
marie.dupont@example.com
+33 6 12 34 56 78
Paris, France

Expérience professionnelle
Ingénieure Logiciel | Tech Solutions
Janvier 2021 - Présent
Développement de microservices en Python.

Formation
Université de Paris
Master en Informatique
Septembre 2019 - Juin 2021
"""
    )
    assert p.personal_info.phone == "+33 6 12 34 56 78"
    assert p.personal_info.location == "Paris, France"
    assert len(p.experience) >= 1
    exp = p.experience[0]
    assert exp.title == "Ingénieure Logiciel"
    assert exp.company == "Tech Solutions"
    assert exp.start_date == date(2021, 1, 1)
    assert exp.is_current is True
    assert len(p.education) >= 1
    assert p.education[0].field_of_study == "Informatique"


# ---------------------------------------------------------------------------
# Text cleaning (PDF/OCR artifacts)
# ---------------------------------------------------------------------------


def test_clean_text_removes_pdf_cid_artifacts() -> None:
    cleaned = clean_text("(cid:127) Jane\nDoe\n(cid:5) Python")
    assert "cid" not in cleaned
    assert "Jane" in cleaned
    assert "Python" in cleaned


def test_clean_text_normalizes_line_endings_and_spaces() -> None:
    cleaned = clean_text("Jane\r\nDoe\r\n\tPython \u00a0Docker")
    assert "\r" not in cleaned
    assert "Python Docker" in cleaned


def test_clean_text_collapses_blank_lines() -> None:
    cleaned = clean_text("Experience\n\n\n\n\nAcme Corp\n\n\n2020 - 2022")
    assert cleaned == "Experience\n\nAcme Corp\n\n2020 - 2022"


def test_clean_text_strips_bullets_and_dashes() -> None:
    cleaned = clean_text("- Led migration.\n\u2022 Built APIs.\n* Fixed bugs.")
    assert cleaned == "Led migration.\nBuilt APIs.\nFixed bugs."


# ---------------------------------------------------------------------------
# Skill dedup
# ---------------------------------------------------------------------------


def test_skills_deduplicated_and_normalized() -> None:
    p = _normalize("Skills\nPython, python, PYTHON, Node.js, nodejs, Postgres")
    names = [s.name for s in p.skills]
    assert names == ["Python", "Node.js", "PostgreSQL"]


# ---------------------------------------------------------------------------
# Empty / minimal input
# ---------------------------------------------------------------------------


def test_normalizer_handles_minimal_text() -> None:
    p = _normalize("John Doe")
    assert p.personal_info.full_name == "John Doe"
    assert p.education == ()
    assert p.experience == ()
    assert p.skills == ()
