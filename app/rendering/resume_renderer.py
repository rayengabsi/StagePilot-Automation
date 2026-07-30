from __future__ import annotations

from pathlib import Path

from app.config.rendering_config import RenderingConfig
from app.rendering.docx_renderer import DocxRenderer
from app.rendering.models import DocumentOutput, RenderContext
from app.rendering.pdf_renderer import PdfRenderer
from app.rendering.template_loader import TemplateDef, TemplateLoader
from app.rendering.theme_loader import ThemeDef, ThemeLoader


class ResumeRenderer:
    def __init__(
        self,
        config: RenderingConfig,
        template_loader: TemplateLoader | None = None,
        theme_loader: ThemeLoader | None = None,
    ) -> None:
        self._config = config
        self._template_loader = template_loader or TemplateLoader()
        self._theme_loader = theme_loader or ThemeLoader()
        self._pdf = PdfRenderer()
        self._docx = DocxRenderer()

    def render(
        self,
        context: RenderContext,
        output_path: Path,
        template_name: str | None = None,
        theme_name: str | None = None,
        fmt: str = "pdf",
    ) -> DocumentOutput:
        tpl = self._load_template(template_name)
        theme = self._load_theme(theme_name)

        if fmt == "pdf":
            return self._pdf.render_resume(context, tpl, theme, output_path)
        if fmt == "docx":
            return self._docx.render_resume(context, tpl, theme, output_path)
        raise ValueError(f"Unsupported format: {fmt}")

    def render_all(
        self,
        context: RenderContext,
        output_dir: Path,
        filename_stem: str = "resume",
        template_name: str | None = None,
        theme_name: str | None = None,
        formats: list[str] | None = None,
    ) -> list[DocumentOutput]:
        fmts = formats or list(self._config.export.default_formats)
        results: list[DocumentOutput] = []
        for fmt in fmts:
            ext = fmt
            out_path = output_dir / f"{filename_stem}.{ext}"
            result = self.render(context, out_path, template_name, theme_name, fmt=fmt)
            results.append(result)
        return results

    def _load_template(self, name: str | None) -> TemplateDef:
        tpl_name = name or self._config.general.default_template
        return self._template_loader.load(tpl_name)

    def _load_theme(self, name: str | None) -> ThemeDef:
        if name:
            return self._theme_loader.load()
        return self._theme_loader.load()
