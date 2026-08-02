from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.jobs import JobSource
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError


class JobSourceRepository:
    """Repository for configured job discovery sources."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a database session."""
        self._session = session

    def add_rss_source(self, name: str, url: str) -> JobSource:
        """Create and persist an active RSS job source."""
        return self.add_source(
            name=name,
            source_type=JobSourceType.RSS_FEED,
            base_url=url,
            config={},
        )

    def add_source(
        self,
        name: str,
        source_type: JobSourceType,
        base_url: str,
        config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> JobSource:
        """Create and persist a job source of any provider type."""
        if not name or not name.strip():
            raise SourceConfigError("source name is required")
        if not base_url or not base_url.strip():
            raise SourceConfigError("source base_url is required")
        source = JobSource(
            name=name,
            type=source_type.value,
            base_url=base_url,
            config_json=dict(config or {}),
            is_active=is_active,
        )
        self._session.add(source)
        self._session.flush()
        return source

    def get_source(self, source_id: int) -> JobSource:
        """Return a single source by ID or raise SourceConfigError."""
        source = self._session.get(JobSource, source_id)
        if source is None:
            raise SourceConfigError(f"Source with id {source_id} not found")
        return source

    def get_source_by_name(self, name: str) -> JobSource | None:
        """Return a single source by unique name, or None."""
        return self._session.scalar(select(JobSource).where(JobSource.name == name))

    def remove_source(self, source_id: int) -> bool:
        """Delete a source by ID; return True if a source was removed."""
        source = self._session.get(JobSource, source_id)
        if source is None:
            return False
        self._session.delete(source)
        self._session.flush()
        return True

    def set_source_active(self, source_id: int, is_active: bool) -> JobSource:
        """Enable or disable a source and return the updated record."""
        source = self.get_source(source_id)
        source.is_active = is_active
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
