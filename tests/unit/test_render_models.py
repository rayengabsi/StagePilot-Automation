from __future__ import annotations

from app.domain.master_profile.entities import (
    Education,
    Experience,
    MasterProfile,
    PersonalInfo,
    Skill,
)
from app.rendering.models import (
    CoverLetterData,
    DocumentOutput,
    RenderContext,
    SectionContent,
    SectionType,
)


def test_render_context_from_profile() -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe", email="john@example.com"),
        education=(Education(institution="MIT", degree="BSc", field_of_study="CS"),),
        experience=(Experience(company="Google", title="SWE"),),
        skills=(Skill(name="Python"),),
    )
    ctx = RenderContext.from_profile(profile)
    assert ctx.personal_info.full_name == "John Doe"
    assert len(ctx.education) == 1
    assert len(ctx.experience) == 1
    assert len(ctx.skills) == 1


def test_render_context_with_tailored_sections() -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Jane Doe"),
    )
    tailored = {"summary": "Experienced developer", "skills": "Python, SQL"}
    ctx = RenderContext.from_profile(profile, tailored_sections=tailored)
    assert ctx.tailored_sections == tailored


def test_document_output_creation() -> None:
    from pathlib import Path

    out = DocumentOutput(
        path=Path("output/resume.pdf"),
        format="pdf",
        page_count=2,
        sections_rendered=5,
        template_used="modern",
        theme_used="default",
    )
    assert out.format == "pdf"
    assert out.sections_rendered == 5


def test_cover_letter_data() -> None:
    data = CoverLetterData(
        body="Cover letter body",
        recipient_name="HR",
        company_name="Acme",
        candidate_name="John Doe",
        job_title="Engineer",
    )
    assert data.body == "Cover letter body"
    assert data.recipient_name == "HR"


def test_section_content() -> None:
    section = SectionContent(
        section_type=SectionType.SKILLS,
        title="Skills",
        items=[{"name": "Python"}, {"name": "SQL"}],
        layout="compact",
    )
    assert section.section_type == SectionType.SKILLS
    assert len(section.items) == 2
