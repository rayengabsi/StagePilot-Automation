from __future__ import annotations

from app.config.rendering_config import get_rendering_config


def test_rendering_config_loads() -> None:
    config = get_rendering_config()
    assert config.general.default_template == "modern"
    assert config.general.default_language == "en"
    assert config.page.page_size == "A4"
    assert config.page.page_width == 595.27


def test_rendering_config_export_formats() -> None:
    config = get_rendering_config()
    assert "pdf" in config.export.default_formats
    assert "docx" in config.export.default_formats


def test_rendering_config_cached() -> None:
    c1 = get_rendering_config()
    c2 = get_rendering_config()
    assert c1 is c2


def test_rendering_config_metadata() -> None:
    config = get_rendering_config()
    assert config.pdf_metadata.author == "StagePilot Automation"
    assert config.pdf_metadata.subject == "Resume / Cover Letter"
