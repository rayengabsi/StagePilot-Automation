from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RENDERING_CONFIG_PATH = Path(__file__).parent / "rendering.toml"


@dataclass(frozen=True, slots=True)
class GeneralConfig:
    default_template: str
    default_theme: str
    default_language: str


@dataclass(frozen=True, slots=True)
class PageConfig:
    page_size: str
    page_width: float
    page_height: float


@dataclass(frozen=True, slots=True)
class FontsConfig:
    font_directory: str
    fallback_family: str


@dataclass(frozen=True, slots=True)
class PdfMetadataConfig:
    author: str
    subject: str
    keywords: str


@dataclass(frozen=True, slots=True)
class ExportConfig:
    default_formats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreviewConfig:
    default_page: int


@dataclass(frozen=True, slots=True)
class RenderingConfig:
    general: GeneralConfig
    page: PageConfig
    fonts: FontsConfig
    pdf_metadata: PdfMetadataConfig
    export: ExportConfig
    preview: PreviewConfig

    @classmethod
    def load(cls, path: Path = RENDERING_CONFIG_PATH) -> RenderingConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        gen = raw["general"]
        page = raw["page"]
        fonts = raw["fonts"]
        meta = raw["pdf_metadata"]
        export = raw["export"]
        prev = raw["preview"]
        return cls(
            general=GeneralConfig(
                default_template=gen["default_template"],
                default_theme=gen["default_theme"],
                default_language=gen["default_language"],
            ),
            page=PageConfig(
                page_size=page["page_size"],
                page_width=float(page["page_width"]),
                page_height=float(page["page_height"]),
            ),
            fonts=FontsConfig(
                font_directory=fonts.get("font_directory", ""),
                fallback_family=fonts.get("fallback_family", "Helvetica"),
            ),
            pdf_metadata=PdfMetadataConfig(
                author=meta["author"],
                subject=meta["subject"],
                keywords=meta["keywords"],
            ),
            export=ExportConfig(
                default_formats=tuple(export.get("default_formats", ["pdf", "docx"])),
            ),
            preview=PreviewConfig(
                default_page=int(prev.get("default_page", 1)),
            ),
        )


@lru_cache(maxsize=1)
def get_rendering_config(path: Path = RENDERING_CONFIG_PATH) -> RenderingConfig:
    """Return cached rendering configuration from rendering.toml."""
    return RenderingConfig.load(path)
