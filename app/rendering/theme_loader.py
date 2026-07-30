from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rendering.template_loader import TemplateDef

THEME_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "theme.toml"


@dataclass(frozen=True, slots=True)
class ThemeDef:
    name: str
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    page_size: str | None = None
    font_family: str | None = None
    font_sizes: dict[str, int] = field(default_factory=dict)
    margins: dict[str, int] = field(default_factory=dict)
    spacing: dict[str, int] = field(default_factory=dict)
    show_icons: bool | None = None
    show_photo: bool | None = None
    columns: int | None = None

    def apply_to(self, template: TemplateDef) -> TemplateDef:
        from app.rendering.template_loader import (
            ColorConfig,
            FontConfig,
            FontStyle,
            SpacingConfig,
            TemplateDef,
        )

        colors = template.colors
        if self.primary_color:
            colors = ColorConfig(
                primary=self.primary_color,
                secondary=self.secondary_color or colors.secondary,
                accent=self.accent_color or colors.accent,
                text=colors.text,
                background=colors.background,
                section_divider=colors.section_divider,
            )

        fonts = template.fonts
        if self.font_family:
            fonts = FontConfig(
                family=self.font_family,
                heading=FontStyle(
                    family=self.font_family,
                    size=self.font_sizes.get("heading", fonts.heading.size),
                    weight=fonts.heading.weight,
                    color=fonts.heading.color,
                ),
                subheading=FontStyle(
                    family=self.font_family,
                    size=self.font_sizes.get("subheading", fonts.subheading.size),
                    weight=fonts.subheading.weight,
                    color=fonts.subheading.color,
                ),
                body=FontStyle(
                    family=self.font_family,
                    size=self.font_sizes.get("body", fonts.body.size),
                    weight=fonts.body.weight,
                    color=fonts.body.color,
                ),
            )

        spacing = template.spacing
        if self.margins:
            spacing = SpacingConfig(
                page_margin_top=self.margins.get("top", spacing.page_margin_top),
                page_margin_bottom=self.margins.get("bottom", spacing.page_margin_bottom),
                page_margin_left=self.margins.get("left", spacing.page_margin_left),
                page_margin_right=self.margins.get("right", spacing.page_margin_right),
                section_gap=self.spacing.get("section_gap", spacing.section_gap),
                line_height=spacing.line_height,
            )

        return TemplateDef(
            name=template.name,
            version=template.version,
            description=template.description,
            fonts=fonts,
            colors=colors,
            spacing=spacing,
            section_styles=template.section_styles,
            header=template.header,
            footer=template.footer,
            section_order=template.section_order,
            page_size=self.page_size or template.page_size,
            columns=self.columns or template.columns,
            show_header=template.show_header,
            show_footer=template.show_footer,
            show_icons=self.show_icons if self.show_icons is not None else template.show_icons,
            show_photo=self.show_photo if self.show_photo is not None else template.show_photo,
        )


class ThemeLoader:
    def __init__(self, path: Path = THEME_CONFIG_PATH) -> None:
        self._path = path

    def load(self) -> ThemeDef:
        if not self._path.exists():
            return ThemeDef(name="default")
        raw = tomllib.loads(self._path.read_text(encoding="utf-8"))
        return ThemeDef(
            name=raw.get("name", "custom"),
            primary_color=raw.get("primary_color"),
            secondary_color=raw.get("secondary_color"),
            accent_color=raw.get("accent_color"),
            page_size=raw.get("page_size"),
            font_family=raw.get("font_family"),
            font_sizes=raw.get("font_sizes", {}),
            margins=raw.get("margins", {}),
            spacing=raw.get("spacing", {}),
            show_icons=raw.get("show_icons"),
            show_photo=raw.get("show_photo"),
            columns=raw.get("columns"),
        )


@lru_cache(maxsize=1)
def load_default_theme(path: Path = THEME_CONFIG_PATH) -> ThemeDef:
    """Load and cache the default theme from config/theme.toml."""
    return ThemeLoader(path).load()
