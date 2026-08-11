from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobFilter(Base):
    """Singleton row holding the user-controlled job filter configuration.

    Exactly one row (id=1) exists at most. The singleton invariant is enforced
    by the application layer — a partial unique index is not portable to MySQL,
    so the DB itself only guarantees a primary key.
    """

    __tablename__ = "job_filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
