from __future__ import annotations

from app.rendering.template_loader import TemplateLoader
from app.rendering.theme_loader import ThemeDef, load_default_theme


def test_default_theme_has_name() -> None:
    theme = load_default_theme()
    assert theme.name == "default"


def test_theme_apply_to_changes_color() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    theme = ThemeDef(
        name="custom",
        primary_color="#ff0000",
    )
    result = theme.apply_to(tpl)
    assert result.colors.primary == "#ff0000"
    assert result.fonts.family == tpl.fonts.family


def test_theme_apply_to_changes_font() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    theme = ThemeDef(
        name="custom",
        font_family="Times-Roman",
        font_sizes={"heading": 20},
    )
    result = theme.apply_to(tpl)
    assert result.fonts.family == "Times-Roman"
    assert result.fonts.heading.size == 20


def test_theme_apply_to_changes_page_size() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    theme = ThemeDef(name="custom", page_size="letter")
    result = theme.apply_to(tpl)
    assert result.page_size == "letter"


def test_theme_apply_to_changes_spacing() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    theme = ThemeDef(name="custom", margins={"top": 100})
    result = theme.apply_to(tpl)
    assert result.spacing.page_margin_top == 100


def test_theme_apply_preserves_unset_values() -> None:
    loader = TemplateLoader()
    tpl = loader.load("modern")
    orig_secondary = tpl.colors.secondary
    orig_accent = tpl.colors.accent
    theme = ThemeDef(name="custom", primary_color="#ff0000")
    result = theme.apply_to(tpl)
    assert result.colors.secondary == orig_secondary
    assert result.colors.accent == orig_accent
