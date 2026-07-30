from __future__ import annotations

from enum import StrEnum


class AIProviderName(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"


class AIFeature(StrEnum):
    EXPLANATION = "explanation"
    RESUME_TAILORING = "resume_tailoring"
    COVER_LETTER = "cover_letter"
    EMAIL_DRAFT = "email_draft"
