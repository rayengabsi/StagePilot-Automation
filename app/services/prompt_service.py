from __future__ import annotations

from pathlib import Path
from string import Template

from app.domain.ai.errors import PromptError

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

_PROMPT_FILES: dict[str, str] = {
    "match_explanation": "match_explanation.md",
    "resume_tailoring": "resume_tailoring.md",
    "cover_letter": "cover_letter.md",
    "email_application": "email_application.md",
}


class PromptService:
    """Load, render, and manage versioned prompt template files."""

    def __init__(self, prompt_dir: Path = PROMPT_DIR) -> None:
        self._prompt_dir = prompt_dir

    def load_prompt(self, name: str) -> str:
        """Load the raw prompt template text by name."""
        filename = _PROMPT_FILES.get(name)
        if not filename:
            raise PromptError(f"Unknown prompt: {name}")
        path = self._prompt_dir / filename
        if not path.exists():
            raise PromptError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def render(self, name: str, variables: dict[str, str]) -> str:
        """Load a prompt template and substitute variables.

        Variables should be pre-serialized to strings.
        """
        template_text = self.load_prompt(name)
        try:
            return Template(template_text).safe_substitute(variables)
        except ValueError as exc:
            raise PromptError(f"Failed to render prompt '{name}': {exc}") from exc

    def get_version(self, name: str) -> str:
        """Extract the version from a prompt file's front matter."""
        raw = self.load_prompt(name)
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
        return "unknown"

    def list_prompts(self) -> list[dict[str, str]]:
        """List all available prompts with metadata."""
        result: list[dict[str, str]] = []
        for name, filename in _PROMPT_FILES.items():
            path = self._prompt_dir / filename
            if path.exists():
                raw = path.read_text(encoding="utf-8")
                version = "unknown"
                purpose = ""
                for line in raw.splitlines():
                    line = line.strip()
                    if line.startswith("version:"):
                        version = line.split(":", 1)[1].strip()
                    if line.startswith("purpose:"):
                        purpose = line.split(":", 1)[1].strip()
                result.append({
                    "name": name, "file": filename,
                    "version": version, "purpose": purpose,
                })
        return result
