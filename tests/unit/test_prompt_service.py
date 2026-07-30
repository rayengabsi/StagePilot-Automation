from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.ai.errors import PromptError
from app.services.prompt_service import PromptService


def test_load_known_prompt() -> None:
    svc = PromptService()
    text = svc.load_prompt("match_explanation")
    assert "version:" in text
    assert "$job_title" in text


def test_load_unknown_prompt() -> None:
    svc = PromptService()
    with pytest.raises(PromptError, match="Unknown prompt"):
        svc.load_prompt("nonexistent")


def test_render_substitutes_variables() -> None:
    svc = PromptService()
    result = svc.render("match_explanation", {"job_title": "Software Engineer", "company": "Acme"})
    assert "Software Engineer" in result
    assert "Acme" in result


def test_render_missing_variables() -> None:
    svc = PromptService()
    result = svc.render("match_explanation", {})
    assert "$job_title" in result
    assert "$company" in result


def test_get_version() -> None:
    svc = PromptService()
    version = svc.get_version("match_explanation")
    assert version == "1.0.0"


def test_get_version_unknown() -> None:
    svc = PromptService()
    with pytest.raises(PromptError):
        svc.get_version("nonexistent")


def test_list_prompts() -> None:
    svc = PromptService()
    prompts = svc.list_prompts()
    names = [p["name"] for p in prompts]
    assert "match_explanation" in names
    assert "resume_tailoring" in names
    assert "cover_letter" in names
    assert "email_application" in names
    for p in prompts:
        assert "version" in p
        assert "purpose" in p


def test_render_cover_letter() -> None:
    svc = PromptService()
    result = svc.render("cover_letter", {
        "candidate_name": "John Doe",
        "job_title": "Engineer",
        "company": "Acme",
        "recipient": "Hiring Manager",
        "matched_skills": "Python",
        "education": "BSc CS",
        "experience": "Software Developer",
    })
    assert "John Doe" in result
    assert "Acme" in result


def test_render_email_application() -> None:
    svc = PromptService()
    result = svc.render("email_application", {
        "recipient": "HR",
        "company": "Acme",
        "job_title": "Engineer",
        "cover_letter_body": "I am a good fit",
        "candidate_name": "John",
    })
    assert "Engineer" in result
    assert "Acme" in result


def test_prompt_dir_missing(tmp_path: Path) -> None:
    svc = PromptService(prompt_dir=tmp_path / "nonexistent")
    with pytest.raises(PromptError, match="Prompt file not found"):
        svc.load_prompt("match_explanation")
