from __future__ import annotations

from pathlib import Path

from app.infrastructure.parsers.abstract import ProfileParser


class MarkdownParser(ProfileParser):
    """Extract text from .md files."""

    def parse(self, file_path: Path) -> str:
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)
        if file_path.suffix.lower() not in {".md", ".markdown"}:
            msg = f"Unsupported extension: {file_path.suffix}"
            raise ValueError(msg)

        text = file_path.read_text(encoding="utf-8")
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("---"):
                continue
            lines.append(stripped)
        return "\n".join(lines)
