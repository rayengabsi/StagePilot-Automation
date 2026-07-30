from __future__ import annotations

from app.main import ApplicationContext, create_application_context


def test_application_context_starts() -> None:
    """The application bootstrap should create a runtime context."""
    context = create_application_context()

    assert isinstance(context, ApplicationContext)
    assert context.settings.app_name == "StagePilot Automation"
    assert context.settings.database_url.startswith("mysql+pymysql://")
