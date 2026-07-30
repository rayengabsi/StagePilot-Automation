from __future__ import annotations

import pytest
from app.rendering.template_loader import TemplateLoader, load_all_templates


def test_template_loader_known_template() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    assert tpl.name == "modern"
    assert tpl.version == "1.0.0"
    assert len(tpl.section_order) > 0
    assert tpl.fonts.family == "Helvetica"


def test_template_loader_all_templates() -> None:
    templates = load_all_templates()
    names = {t["name"] for t in templates}
    for expected in ("modern", "executive", "minimal", "classic", "professional"):
        assert expected in names, f"Missing template: {expected}"


def test_template_loader_unknown_raises() -> None:
    loader = TemplateLoader()
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent_template")


def test_modern_template_has_section_styles() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    assert "summary" in tpl.section_styles
    assert "skills" in tpl.section_styles
    assert "experience" in tpl.section_styles


def test_executive_template_has_serif_font() -> None:
    loader = TemplateLoader()
    tpl = loader.load("executive")
    assert tpl.fonts.family == "Times-Roman"


def test_minimal_template_no_footer() -> None:
    loader = TemplateLoader()
    tpl = loader.load("minimal")
    assert tpl.show_footer is False


def test_classic_template_black_colors() -> None:
    loader = TemplateLoader()
    tpl = loader.load("classic")
    assert tpl.colors.primary == "#000000"
    assert tpl.colors.text == "#000000"


def test_professional_template_has_accent() -> None:
    loader = TemplateLoader()
    tpl = loader.load("professional")
    assert tpl.colors.accent == "#2980b9"


def test_template_list_returns_metadata() -> None:
    templates = load_all_templates()
    for t in templates:
        assert "name" in t
        assert "version" in t
        assert "description" in t
