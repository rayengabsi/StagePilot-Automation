from __future__ import annotations

import pytest
from app.db.base import Base, import_models
from app.db.models.jobs import JobSource
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.services.job_source_repository import JobSourceRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> Session:
    """Create an isolated in-memory session with all models loaded."""
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_add_source_creates_provider_source(session: Session) -> None:
    """add_source should persist a source with provider config."""
    repo = JobSourceRepository(session)
    source = repo.add_source(
        name="Acme Greenhouse",
        source_type=JobSourceType.GREENHOUSE,
        base_url="https://boards.greenhouse.io/acme",
        config={"token": "acme"},
    )

    assert source.id is not None
    assert source.type == "greenhouse"
    assert source.config_json == {"token": "acme"}
    assert source.is_active is True


def test_add_source_rejects_missing_url(session: Session) -> None:
    """add_source should reject a source without a base URL."""
    repo = JobSourceRepository(session)

    with pytest.raises(SourceConfigError):
        repo.add_source(
            name="Broken",
            source_type=JobSourceType.LEVER,
            base_url="",
        )


def test_remove_source_deletes(session: Session) -> None:
    """remove_source should delete a source and return True."""
    repo = JobSourceRepository(session)
    source = repo.add_source(
        name="Temp",
        source_type=JobSourceType.REMOTE_OK,
        base_url="https://remoteok.com",
    )

    removed = repo.remove_source(source.id)

    assert removed is True
    assert session.scalar(select(JobSource).where(JobSource.id == source.id)) is None
    assert repo.remove_source(source.id) is False


def test_set_source_active_toggles(session: Session) -> None:
    """set_source_active should flip the active flag."""
    repo = JobSourceRepository(session)
    source = repo.add_source(
        name="Toggle",
        source_type=JobSourceType.RSS_FEED,
        base_url="https://example.com/feed",
    )

    disabled = repo.set_source_active(source.id, False)
    assert disabled.is_active is False

    enabled = repo.set_source_active(source.id, True)
    assert enabled.is_active is True


def test_list_active_configs_filters_inactive(session: Session) -> None:
    """Only active sources should appear in list_active_configs."""
    repo = JobSourceRepository(session)
    active = repo.add_source(
        name="Active",
        source_type=JobSourceType.RSS_FEED,
        base_url="https://example.com/a",
    )
    inactive = repo.add_source(
        name="Inactive",
        source_type=JobSourceType.RSS_FEED,
        base_url="https://example.com/i",
    )
    repo.set_source_active(inactive.id, False)

    configs = repo.list_active_configs()

    names = [config.name for config in configs]
    assert names == [active.name]
