"""Deterministic preprocessing of raw resume text extracted from documents.

This module normalizes text that is produced by PDF/DOCX extraction so the
section-splitting and extraction rules in :class:`ProfileNormalizer` receive
clean, consistent input. It is pure and has no dependencies outside the
standard library.
"""

from __future__ import annotations

import re

# PDF extraction artifacts such as "(cid:127)" from embedded fonts.
_CID_ARTIFACT_RE = re.compile(r"\(\s*cid[: ]?\d+\s*\)")

# Unicode and ASCII bullet / list markers at the start of a line.
_BULLET_RE = re.compile(
    r"^\s*(?:"
    r"\u2022|\u25cf|\u25e6|\u2023|\u00b7|\u2043|\u25aa|\u25b8|\u25c6|\u2713|\u2714|"
    r"\u25cf|\u2022|\u2192|\u21d2|\u00bb|\u276f|\u2043|\u2212|"
    r"[*>\-\u2013\u2014\u2022\u25cf]"
    r")\s*"
)

# Horizontal ellipsis and other repeated punctuation noise.
_NOISE_RE = re.compile(r"[.]{3,}")

# Non-breaking space, zero-width characters.
_NBSP_RE = re.compile(r"[\u00a0\u200b\u202f\u2060]")


def clean(text: str) -> str:
    """Return a cleaned, line-normalized copy of ``text``.

    Handles:
      - ``(cid:N)`` extraction artifacts
      - Unicode/ASCII bullets and list markers
      - Broken line endings (CRLF, lone CR)
      - Non-breaking and zero-width spaces
      - Collapsed multiple blank lines and stray internal spaces
      - Control characters and OCR noise
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _NBSP_RE.sub(" ", text)
    text = _CID_ARTIFACT_RE.sub(" ", text)
    # Normalize en-dash / em-dash used in date ranges to plain hyphens.
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = _NOISE_RE.sub("...", text)
    # Drop control characters (keeping tabs and newlines).
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)

    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = _BULLET_RE.sub("", raw_line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            cleaned_lines.append("")
        else:
            cleaned_lines.append(line)

    joined = "\n".join(cleaned_lines)
    # Collapse runs of three or more blank lines into a single blank line.
    joined = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", joined)
    return joined.strip()
