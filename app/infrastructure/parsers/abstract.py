from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ProfileParser(ABC):
    """Abstract interface for resume/profile document parsers.

    Parsers extract raw text from a document file.
    They do NOT perform normalization, validation, or business logic.
    """

    @abstractmethod
    def parse(self, file_path: Path) -> str:
        """Extract raw text content from the given document file.

        Args:
            file_path: Path to the document file (e.g. PDF, DOCX).

        Returns:
            Raw text content extracted from the document.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is not supported or parsing fails.
        """
