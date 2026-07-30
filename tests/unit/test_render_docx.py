from __future__ import annotations

from pathlib import Path

from app.domain.master_profile.entities import (
    Education,
    Experience,
    MasterProfile,
    PersonalInfo,
    Skill,
)
from app.rendering.docx_renderer import DocxRenderer
from app.rendering.models import CoverLetterData, RenderContext
from app.rendering.template_loader import TemplateLoader
from app.rendering.theme_loader import ThemeDef


def test_docx_render_resume_creates_file(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe", email="john@example.com"),
        education=(Education(institution="MIT", degree="BSc", field_of_study="CS"),),
        experience=(Experience(company="Google", title="SWE", description="Built APIs"),),
        skills=(Skill(name="Python"), Skill(name="SQL")),
    )
    context = RenderContext.from_profile(profile)
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "resume.docx"

    renderer = DocxRenderer()
    result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert result.format == "docx"


def test_docx_render_cover_letter_creates_file(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Jane Doe"),
    )
    context = RenderContext.from_profile(profile)
    cover_data = CoverLetterData(
        body="Dear Hiring Manager,\n\nI am writing to apply.",
        recipient_name="HR",
        candidate_name="Jane Doe",
    )
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "cover_letter.docx"

    renderer = DocxRenderer()
    result = renderer.render_cover_letter(context, cover_data, template, theme, out_path)

    assert out_path.exists()
    assert result.format == "docx"


def test_docx_render_with_tailored_sections(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe"),
        skills=(Skill(name="Python"),),
    )
    tailored = {"summary": "Experienced developer.", "skills": "Python, SQL"}
    context = RenderContext.from_profile(profile, tailored_sections=tailored)
    template = TemplateLoader().load("professional")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "tailored.docx"

    renderer = DocxRenderer()
    result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert result.sections_rendered >= 2


def test_docx_render_empty_profile(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="No Data"),
    )
    context = RenderContext.from_profile(profile)
    template = TemplateLoader().load("minimal")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "empty.docx"

    renderer = DocxRenderer()
    _result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
