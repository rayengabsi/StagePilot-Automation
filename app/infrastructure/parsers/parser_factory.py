from __future__ import annotations

from pathlib import Path

from app.infrastructure.parsers.abstract import ProfileParser
from app.infrastructure.parsers.docx_parser import DocxParser
from app.infrastructure.parsers.markdown_parser import MarkdownParser
from app.infrastructure.parsers.pdf_parser import PDFParser


def detect_parser(file_path: str | Path) -> ProfileParser:
    """Auto-detect file type and return the appropriate parser."""
    path = Path(file_path) if isinstance(file_path, str) else file_path
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return PDFParser()
    if suffix in {".docx", ".doc"}:
        return DocxParser()
    if suffix in {".md", ".markdown"}:
        return MarkdownParser()

    msg = f"Unsupported file format: {suffix}. Supported: .pdf, .docx, .doc, .md"
    raise ValueError(msg)
