from __future__ import annotations

from pathlib import Path

from app.domain.master_profile.entities import (
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    ProficiencyLevel,
    Skill,
)
from app.rendering.models import CoverLetterData, RenderContext
from app.rendering.pdf_renderer import PdfRenderer
from app.rendering.template_loader import TemplateLoader
from app.rendering.theme_loader import ThemeDef


def test_pdf_render_resume_creates_file(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe", email="john@example.com"),
        education=(Education(institution="MIT", degree="BSc", field_of_study="CS"),),
        experience=(Experience(company="Google", title="SWE", description="Built APIs"),),
        skills=(Skill(name="Python"), Skill(name="SQL")),
        languages=(Language(name="English", proficiency=ProficiencyLevel.NATIVE),),
    )
    context = RenderContext.from_profile(profile)
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "resume.pdf"

    renderer = PdfRenderer()
    result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert result.format == "pdf"
    assert result.sections_rendered > 0


def test_pdf_render_cover_letter_creates_file(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Jane Doe"),
    )
    context = RenderContext.from_profile(profile)
    cover_data = CoverLetterData(
        body="Dear Hiring Manager,\n\nI am writing to apply.",
        recipient_name="HR",
        company_name="Acme",
        candidate_name="Jane Doe",
        job_title="Engineer",
    )
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "cover_letter.pdf"

    renderer = PdfRenderer()
    result = renderer.render_cover_letter(context, cover_data, template, theme, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert result.format == "pdf"


def test_pdf_render_with_tailored_sections(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe"),
        skills=(Skill(name="Python"),),
    )
    tailored = {
        "summary": "Experienced Python developer with 5 years experience.",
        "skills": "Python, FastAPI, SQL",
    }
    context = RenderContext.from_profile(profile, tailored_sections=tailored)
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "tailored_resume.pdf"

    renderer = PdfRenderer()
    result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert result.sections_rendered >= 2


def test_pdf_render_empty_profile(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="No Data"),
    )
    context = RenderContext.from_profile(profile)
    template = TemplateLoader().load("minimal")
    theme = ThemeDef(name="default")
    out_path = tmp_path / "empty.pdf"

    renderer = PdfRenderer()
    _result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_pdf_render_with_theme_override(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Themed User"),
    )
    context = RenderContext.from_profile(profile)
    template = TemplateLoader().load("modern")
    theme = ThemeDef(name="custom", primary_color="#ff0000", page_size="letter")
    out_path = tmp_path / "themed.pdf"

    renderer = PdfRenderer()
    result = renderer.render_resume(context, template, theme, out_path)

    assert out_path.exists()
    assert result.template_used == "modern"
    assert result.theme_used == "custom"
