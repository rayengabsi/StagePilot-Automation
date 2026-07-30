from __future__ import annotations

from pathlib import Path

import pytest
from app.infrastructure.parsers.pdf_parser import PDFParser


def test_pdf_parser_raises_on_missing_file() -> None:
    parser = PDFParser()
    with pytest.raises(FileNotFoundError):
        parser.parse(Path("/nonexistent/file.pdf"))


def test_pdf_parser_raises_on_wrong_extension(tmp_path: Path) -> None:
    parser = PDFParser()
    f = tmp_path / "resume.txt"
    f.write_text("not a pdf")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        parser.parse(f)


def test_pdf_parser_accepts_pdf_extension() -> None:
    parser = PDFParser()
    assert ".pdf" in parser.SUPPORTED_EXTENSIONS
