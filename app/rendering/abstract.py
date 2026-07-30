from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.rendering.models import CoverLetterData, DocumentOutput, RenderContext
from app.rendering.template_loader import TemplateDef
from app.rendering.theme_loader import ThemeDef


class DocumentRenderer(ABC):
    @abstractmethod
    def render_resume(
        self,
        context: RenderContext,
        template: TemplateDef,
        theme: ThemeDef,
        output_path: Path,
    ) -> DocumentOutput: ...

    @abstractmethod
    def render_cover_letter(
        self,
        context: RenderContext,
        cover_data: CoverLetterData,
        template: TemplateDef,
        theme: ThemeDef,
        output_path: Path,
    ) -> DocumentOutput: ...
