from __future__ import annotations

from pathlib import Path

from app.config.rendering_config import RenderingConfig, get_rendering_config
from app.domain.master_profile.entities import MasterProfile
from app.rendering.cover_letter_renderer import CoverLetterRenderer
from app.rendering.models import CoverLetterData, DocumentOutput, RenderContext
from app.rendering.resume_renderer import ResumeRenderer
from app.rendering.template_loader import TemplateLoader, load_all_templates
from app.rendering.theme_loader import ThemeLoader


class RendererFactory:
    def __init__(self, config: RenderingConfig | None = None) -> None:
        self._config = config or get_rendering_config()
        self._template_loader = TemplateLoader()
        self._theme_loader = ThemeLoader()
        self._resume_renderer = ResumeRenderer(
            self._config, self._template_loader, self._theme_loader
        )
        self._cover_renderer = CoverLetterRenderer(
            self._config, self._template_loader, self._theme_loader
        )

    def render_resume(
        self,
        profile: MasterProfile,
        output_path: Path,
        template_name: str | None = None,
        theme_name: str | None = None,
        tailored_sections: dict[str, str] | None = None,
        fmt: str = "pdf",
    ) -> DocumentOutput:
        context = RenderContext.from_profile(profile, tailored_sections=tailored_sections)
        return self._resume_renderer.render(
            context, output_path, template_name, theme_name, fmt=fmt
        )

    def render_resume_all(
        self,
        profile: MasterProfile,
        output_dir: Path,
        template_name: str | None = None,
        theme_name: str | None = None,
        tailored_sections: dict[str, str] | None = None,
        formats: list[str] | None = None,
    ) -> list[DocumentOutput]:
        context = RenderContext.from_profile(profile, tailored_sections=tailored_sections)
        return self._resume_renderer.render_all(
            context, output_dir, template_name=template_name, theme_name=theme_name, formats=formats
        )

    def render_cover_letter(
        self,
        profile: MasterProfile,
        cover_data: CoverLetterData,
        output_path: Path,
        template_name: str | None = None,
        theme_name: str | None = None,
        fmt: str = "pdf",
    ) -> DocumentOutput:
        context = RenderContext.from_profile(profile)
        return self._cover_renderer.render(
            context, cover_data, output_path, template_name, theme_name, fmt=fmt
        )

    def render_cover_letter_all(
        self,
        profile: MasterProfile,
        cover_data: CoverLetterData,
        output_dir: Path,
        template_name: str | None = None,
        theme_name: str | None = None,
        formats: list[str] | None = None,
    ) -> list[DocumentOutput]:
        context = RenderContext.from_profile(profile)
        return self._cover_renderer.render_all(
            context,
            cover_data,
            output_dir,
            template_name=template_name,
            theme_name=theme_name,
            formats=formats,
        )

    def list_templates(self) -> list[dict[str, str]]:
        return load_all_templates()

    def list_themes(self) -> list[dict[str, str]]:
        theme = self._theme_loader.load()
        return [{"name": theme.name, "description": "Custom theme from config/theme.toml"}]


def render_document(
    profile: MasterProfile,
    output_dir: Path,
    document_type: str = "resume",
    template_name: str | None = None,
    theme_name: str | None = None,
    formats: list[str] | None = None,
    tailored_sections: dict[str, str] | None = None,
    cover_data: CoverLetterData | None = None,
) -> list[DocumentOutput]:
    """Render a document (resume or cover letter) to configured formats."""
    factory = RendererFactory()
    if document_type == "resume":
        return factory.render_resume_all(
            profile, output_dir, template_name, theme_name, tailored_sections, formats
        )
    if document_type == "cover_letter":
        if not cover_data:
            raise ValueError("cover_data required for cover_letter rendering")
        return factory.render_cover_letter_all(
            profile, cover_data, output_dir, template_name, theme_name, formats
        )
    raise ValueError(f"Unknown document type: {document_type}")
