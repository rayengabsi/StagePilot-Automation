from __future__ import annotations

from pathlib import Path

from app.domain.master_profile.entities import (
    MasterProfile,
    PersonalInfo,
    Skill,
)
from app.rendering.models import CoverLetterData
from app.rendering.renderer_factory import RendererFactory


def test_factory_list_templates() -> None:
    factory = RendererFactory()
    templates = factory.list_templates()
    names = {t["name"] for t in templates}
    assert "modern" in names
    assert "executive" in names


def test_factory_render_resume_pdf(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe"),
        skills=(Skill(name="Python"),),
    )
    factory = RendererFactory()
    result = factory.render_resume(profile, tmp_path / "resume.pdf")
    assert result.path.exists()
    assert result.format == "pdf"
    assert result.template_used == "modern"


def test_factory_render_resume_docx(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe"),
    )
    factory = RendererFactory()
    result = factory.render_resume(profile, tmp_path / "resume.docx", fmt="docx")
    assert result.path.exists()
    assert result.format == "docx"


def test_factory_render_resume_all(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe"),
    )
    factory = RendererFactory()
    results = factory.render_resume_all(profile, tmp_path)
    assert len(results) == 2
    formats = {r.format for r in results}
    assert formats == {"pdf", "docx"}


def test_factory_render_cover_letter(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Jane Doe"),
    )
    cover_data = CoverLetterData(
        body="Cover letter body.",
        candidate_name="Jane Doe",
    )
    factory = RendererFactory()
    result = factory.render_cover_letter(
        profile, cover_data, tmp_path / "cover.pdf"
    )
    assert result.path.exists()
    assert result.format == "pdf"


def test_factory_list_themes() -> None:
    factory = RendererFactory()
    themes = factory.list_themes()
    assert len(themes) >= 1
    assert themes[0]["name"] == "default"
