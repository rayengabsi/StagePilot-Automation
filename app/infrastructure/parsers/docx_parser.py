from __future__ import annotations

from pathlib import Path

from app.infrastructure.parsers.abstract import ProfileParser


class DocxParser(ProfileParser):
    """Extract text from .docx files using python-docx."""

    def parse(self, file_path: Path) -> str:
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)
        if file_path.suffix.lower() not in {".docx", ".doc"}:
            msg = f"Unsupported extension: {file_path.suffix}"
            raise ValueError(msg)

        from docx import Document

        doc = Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
