from __future__ import annotations

from app.shared.hashing import stable_sha256


def test_stable_sha256_normalizes_whitespace_and_case() -> None:
    """Hashing should be stable for equivalent text payloads."""
    first = stable_sha256({"title": " Software   Internship ", "company": "Example"})
    second = stable_sha256({"company": "example", "title": "software internship"})

    assert first == second
