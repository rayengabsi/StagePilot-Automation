from __future__ import annotations

from pathlib import Path

import pdfplumber

from app.infrastructure.parsers.abstract import ProfileParser
from app.utils.text_cleaning import clean as clean_text


class PDFParser(ProfileParser):
    """Parse PDF documents using pdfplumber."""

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

    def parse(self, file_path: Path) -> str:
        """Extract text from a PDF file using pdfplumber.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Raw text content extracted from all pages.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a PDF or parsing fails.
        """
        resolved = Path(file_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"PDF file not found: {resolved}")
        if resolved.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {resolved.suffix}. Expected: .pdf")

        try:
            pages: list[str] = []
            with pdfplumber.open(resolved) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            if not pages:
                return ""
            return clean_text("\n\n".join(pages))
        except Exception as exc:
            raise ValueError(f"Failed to parse PDF {resolved}: {exc}") from exc
