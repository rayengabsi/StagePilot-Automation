from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from app.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _get_settings() -> Settings:
    return get_settings()


_session_factory_override: sessionmaker[Session] | None = None


def set_session_factory(factory: sessionmaker[Session] | None) -> None:
    """Allow CLI and tests to inject a session factory."""
    global _session_factory_override
    _session_factory_override = factory


def get_db() -> Iterator[Session]:
    """Yield a per-request DB session, closed automatically."""
    from app.db.session import create_database_engine, create_session_factory, session_scope

    factory = _session_factory_override
    if factory is not None:
        with session_scope(factory) as session:
            yield session
        return

    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            yield session
    finally:
        engine.dispose()
