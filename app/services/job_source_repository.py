from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.jobs import JobSource
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType


class JobSourceRepository:
    """Repository for configured job discovery sources."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a database session."""
        self._session = session

    def add_rss_source(self, name: str, url: str) -> JobSource:
        """Create and persist an active RSS job source."""
        source = JobSource(
            name=name,
            type=JobSourceType.RSS_FEED.value,
            base_url=url,
            config_json={},
            is_active=True,
        )
        self._session.add(source)
        self._session.flush()
        return source

    def list_sources(self) -> Sequence[JobSource]:
        """Return all configured job sources ordered by ID."""
        return self._session.scalars(select(JobSource).order_by(JobSource.id)).all()

    def list_active_configs(self) -> list[JobSourceConfig]:
        """Return active sources as connector configuration objects."""
        sources = self._session.scalars(
            select(JobSource).where(JobSource.is_active.is_(True)).order_by(JobSource.id)
        ).all()
        return [
            JobSourceConfig(
                id=source.id,
                name=source.name,
                type=JobSourceType(source.type),
                base_url=source.base_url,
                config=source.config_json,
            )
            for source in sources
        ]
