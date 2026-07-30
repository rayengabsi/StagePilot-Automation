from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.infrastructure.parsers.docx_parser import DocxParser
from app.infrastructure.parsers.markdown_parser import MarkdownParser
from app.infrastructure.parsers.parser_factory import detect_parser
from app.infrastructure.parsers.pdf_parser import PDFParser


class TestPDFParser:
    def test_parse_returns_text(self, tmp_path: Path) -> None:
        path = tmp_path / "resume.pdf"
        path.write_bytes(b"%PDF-1.4 fake content")
        parser = PDFParser()
        with patch("pdfplumber.open") as mock_open:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "John Doe\nPython, Java"
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf
            text = parser.parse(path)
        assert isinstance(text, str)
        assert "John Doe" in text

    def test_parse_file_not_found(self) -> None:
        parser = PDFParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("/nonexistent/file.pdf"))

    def test_parse_wrong_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "resume.txt"
        path.write_text("hello")
        parser = PDFParser()
        with pytest.raises(ValueError, match="Unsupported file extension"):
            parser.parse(path)

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.pdf"
        path.write_bytes(b"%PDF-1.4")
        parser = PDFParser()
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = []
            mock_open.return_value.__enter__.return_value = mock_pdf
            text = parser.parse(path)
        assert text == ""

    def test_supported_extensions(self) -> None:
        parser = PDFParser()
        assert hasattr(parser, "SUPPORTED_EXTENSIONS")


class TestDocxParser:
    def test_parse_file_not_found(self) -> None:
        parser = DocxParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("/nonexistent/file.docx"))

    def test_parse_wrong_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "resume.pdf"
        path.write_bytes(b"fake")
        parser = DocxParser()
        with pytest.raises(ValueError, match="Unsupported extension"):
            parser.parse(path)


class TestMarkdownParser:
    def test_parse_returns_text(self, tmp_path: Path) -> None:
        md_content = """John Doe
john@example.com

## Education
University of Tunis

## Skills
Python, Java, SQL
"""
        path = tmp_path / "resume.md"
        path.write_text(md_content, encoding="utf-8")
        parser = MarkdownParser()
        text = parser.parse(path)
        assert "John Doe" in text
        assert "Education" in text
        assert "Python" in text

    def test_parse_file_not_found(self) -> None:
        parser = MarkdownParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("/nonexistent/file.md"))

    def test_parse_wrong_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "resume.txt"
        path.write_text("hello")
        parser = MarkdownParser()
        with pytest.raises(ValueError, match="Unsupported extension"):
            parser.parse(path)

    def test_parse_strips_frontmatter(self, tmp_path: Path) -> None:
        md_content = """---
name: John
---
Content here
"""
        path = tmp_path / "resume.md"
        path.write_text(md_content, encoding="utf-8")
        parser = MarkdownParser()
        text = parser.parse(path)
        assert "---" not in text
        assert "Content here" in text

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.md"
        path.write_text("", encoding="utf-8")
        parser = MarkdownParser()
        text = parser.parse(path)
        assert text == ""


class TestParserFactory:
    def test_detect_pdf(self) -> None:
        parser = detect_parser("resume.pdf")
        assert isinstance(parser, PDFParser)

    def test_detect_docx(self) -> None:
        parser = detect_parser("resume.docx")
        assert isinstance(parser, DocxParser)

    def test_detect_doc(self) -> None:
        parser = detect_parser("resume.doc")
        assert isinstance(parser, DocxParser)

    def test_detect_markdown(self) -> None:
        parser = detect_parser("resume.md")
        assert isinstance(parser, MarkdownParser)

    def test_detect_markdown_long(self) -> None:
        parser = detect_parser("resume.markdown")
        assert isinstance(parser, MarkdownParser)

    def test_detect_unsupported(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file format"):
            detect_parser("resume.txt")

    def test_detect_unsupported_xml(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file format"):
            detect_parser("resume.xml")
