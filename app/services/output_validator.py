from __future__ import annotations

import json
import re

from app.domain.ai.errors import ValidationError

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"system\s*(prompt|instruction|message)", re.IGNORECASE),
    re.compile(r"You\s+are\s+(now\s+)?(an?\s+)?(free|unrestricted)", re.IGNORECASE),
    re.compile(r"Do\s+(not\s+)?(any|what)ever", re.IGNORECASE),
]


class OutputValidator:
    """Deterministic validation of AI-generated outputs.

    Validates that outputs meet basic quality and safety requirements
    without using any AI or ML-based detection.
    """

    MIN_TEXT_LENGTH = 10

    def validate_text(self, text: str) -> None:
        """Validate a free-text AI output.

        Raises ValidationError if the text fails any check.
        """
        if not text or not text.strip():
            raise ValidationError("AI output is empty")

        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            raise ValidationError(f"AI output too short ({len(text.strip())} chars)")

        self._check_injection(text)

    def validate_json(self, text: str, required_fields: list[str]) -> dict[str, object]:
        """Validate an AI output that should be valid JSON with required fields.

        Returns the parsed JSON dict on success.
        """
        self.validate_text(text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"AI output is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValidationError("AI output JSON is not a dict")

        for field in required_fields:
            if field not in data:
                raise ValidationError(f"AI output JSON missing required field: '{field}'")
            if data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
                raise ValidationError(f"AI output JSON field '{field}' is empty")

        return data

    def _check_injection(self, text: str) -> None:
        """Check for prompt injection attempts in the output."""
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                raise ValidationError(
                    f"AI output contains potential prompt injection pattern: '{match.group()[:60]}'"
                )
