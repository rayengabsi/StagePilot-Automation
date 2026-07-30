from __future__ import annotations

from app.db.base import import_models


def test_approval_tables_importable() -> None:
    import_models()
    from app.db.base import Base

    tables = Base.metadata.tables
    assert "application_packages" in tables
    assert "approval_queue" in tables
    assert "approval_events" in tables
    assert "approval_comments" in tables


def test_application_packages_columns() -> None:
    from app.db.base import Base

    table = Base.metadata.tables["application_packages"]
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert "recommendation_id" in cols
    assert "job_id" in cols
    assert "profile_id" in cols
    assert "final_score" in cols
    assert "status" in cols
    assert "priority" in cols
    assert "revision_number" in cols
    assert "telegram_message_id" in cols
    assert "snapshot_json" in cols
    assert "documents_json" in cols
    assert "application_hash" in cols
    assert "created_at" in cols
    assert "updated_at" in cols
    assert "approved_at" in cols
    assert "reviewed_at" in cols


def test_approval_queue_columns() -> None:
    from app.db.base import Base

    table = Base.metadata.tables["approval_queue"]
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert "package_id" in cols
    assert "queue_order" in cols
    assert "score" in cols
    assert "deadline" in cols
    assert "created_at" in cols


def test_approval_events_columns() -> None:
    from app.db.base import Base

    table = Base.metadata.tables["approval_events"]
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert "package_id" in cols
    assert "action" in cols
    assert "actor" in cols
    assert "comment" in cols
    assert "previous_state" in cols
    assert "new_state" in cols
    assert "created_at" in cols


def test_approval_comments_columns() -> None:
    from app.db.base import Base

    table = Base.metadata.tables["approval_comments"]
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert "package_id" in cols
    assert "author" in cols
    assert "text" in cols
    assert "created_at" in cols
