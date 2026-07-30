from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def import_models() -> None:
    """Import ORM models so Alembic can discover metadata."""
    import app.db.models  # noqa: F401
