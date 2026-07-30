from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


@dataclass(frozen=True, slots=True)
class FontStyle:
    family: str
    size: int
    weight: str = "normal"
    color: str = "#333333"


@dataclass(frozen=True, slots=True)
class FontConfig:
    family: str
    heading: FontStyle
    subheading: FontStyle
    body: FontStyle


@dataclass(frozen=True, slots=True)
class ColorConfig:
    primary: str
    secondary: str
    accent: str
    text: str
    background: str
    section_divider: str = "#cccccc"


@dataclass(frozen=True, slots=True)
class SpacingConfig:
    page_margin_top: int
    page_margin_bottom: int
    page_margin_left: int
    page_margin_right: int
    section_gap: int
    line_height: float


@dataclass(frozen=True, slots=True)
class SectionStyle:
    show_divider: bool
    icon: str | None = None
    layout: str = "standard"


@dataclass(frozen=True, slots=True)
class HeaderStyle:
    alignment: str
    show_name: bool = True
    show_title: bool = True


@dataclass(frozen=True, slots=True)
class FooterStyle:
    alignment: str
    show_page_number: bool = True


@dataclass(frozen=True, slots=True)
class TemplateDef:
    name: str
    version: str
    description: str
    fonts: FontConfig
    colors: ColorConfig
    spacing: SpacingConfig
    section_styles: dict[str, SectionStyle]
    header: HeaderStyle
    footer: FooterStyle
    section_order: tuple[str, ...]
    page_size: str = "A4"
    columns: int = 1
    show_header: bool = True
    show_footer: bool = True
    show_icons: bool = False
    show_photo: bool = False


class TemplateLoader:
    def __init__(self, template_dir: Path = TEMPLATE_DIR) -> None:
        self._template_dir = template_dir

    def load(self, name: str) -> TemplateDef:
        path = self._template_dir / name / "template.json"
        if not path.exists():
            raise FileNotFoundError(f"Template '{name}' not found at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return self._parse(raw)

    def list_templates(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        if not self._template_dir.exists():
            return result
        for child in sorted(self._template_dir.iterdir()):
            if child.is_dir():
                tpl_path = child / "template.json"
                if tpl_path.exists():
                    raw = json.loads(tpl_path.read_text(encoding="utf-8"))
                    result.append(
                        {
                            "name": raw.get("name", child.name),
                            "version": raw.get("version", "unknown"),
                            "description": raw.get("description", ""),
                        }
                    )
        return result

    def _parse(self, raw: dict) -> TemplateDef:
        fonts_raw = raw.get("fonts", {})
        colors_raw = raw.get("colors", {})
        spacing_raw = raw.get("spacing", {})
        header_raw = raw.get("header", {})
        footer_raw = raw.get("footer", {})

        f = fonts_raw
        default_h = {"family": "Helvetica", "size": 16, "weight": "bold", "color": "#000000"}
        default_sh = {"family": "Helvetica", "size": 12, "weight": "bold", "color": "#333333"}
        default_b = {"family": "Helvetica", "size": 10, "weight": "normal", "color": "#333333"}
        fc = FontConfig(
            family=f.get("family", "Helvetica"),
            heading=FontStyle(**f.get("heading", default_h)),
            subheading=FontStyle(**f.get("subheading", default_sh)),
            body=FontStyle(**f.get("body", default_b)),
        )

        cc = ColorConfig(
            primary=colors_raw.get("primary", "#1a1a2e"),
            secondary=colors_raw.get("secondary", "#16213e"),
            accent=colors_raw.get("accent", "#0f3460"),
            text=colors_raw.get("text", "#333333"),
            background=colors_raw.get("background", "#ffffff"),
            section_divider=colors_raw.get("section_divider", "#cccccc"),
        )

        sc = SpacingConfig(
            page_margin_top=int(spacing_raw.get("page_margin_top", 50)),
            page_margin_bottom=int(spacing_raw.get("page_margin_bottom", 50)),
            page_margin_left=int(spacing_raw.get("page_margin_left", 50)),
            page_margin_right=int(spacing_raw.get("page_margin_right", 50)),
            section_gap=int(spacing_raw.get("section_gap", 20)),
            line_height=float(spacing_raw.get("line_height", 1.15)),
        )

        section_styles_raw = raw.get("section_styles", {})
        section_styles: dict[str, SectionStyle] = {}
        for key, val in section_styles_raw.items():
            section_styles[key] = SectionStyle(
                show_divider=val.get("show_divider", True),
                icon=val.get("icon"),
                layout=val.get("layout", "standard"),
            )

        return TemplateDef(
            name=raw.get("name", "unknown"),
            version=raw.get("version", "1.0.0"),
            description=raw.get("description", ""),
            fonts=fc,
            colors=cc,
            spacing=sc,
            section_styles=section_styles,
            header=HeaderStyle(
                alignment=header_raw.get("alignment", "center"),
                show_name=header_raw.get("show_name", True),
                show_title=header_raw.get("show_title", True),
            ),
            footer=FooterStyle(
                alignment=footer_raw.get("alignment", "center"),
                show_page_number=footer_raw.get("show_page_number", True),
            ),
            section_order=tuple(
                raw.get(
                    "section_order",
                    [
                        "summary",
                        "skills",
                        "experience",
                        "education",
                        "projects",
                        "languages",
                        "certifications",
                    ],
                )
            ),
            page_size=raw.get("page_size", "A4"),
            columns=int(raw.get("columns", 1)),
            show_header=bool(raw.get("show_header", True)),
            show_footer=bool(raw.get("show_footer", True)),
            show_icons=bool(raw.get("show_icons", False)),
            show_photo=bool(raw.get("show_photo", False)),
        )


def load_all_templates() -> list[dict[str, str]]:
    """List all available templates with metadata."""
    return TemplateLoader().list_templates()
