"""``exports``: files the panel builds from measurements (ТЗ п. 9, T-30…T-33).

The file lives in the row until ``expires_at``: the API and the Celery worker of T-33 share the
database, not a disk. An export belongs to the user who made it and is served only to him; the
rows inside it were read under his scope (ADR-008).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, LargeBinary
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.models.base import Base, TimestampMixin


class Export(TimestampMixin, Base):
    """One export: its request, the state of its file and the file itself."""

    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint("mode IN ('raw', 'aggregates', 'school_report')", name="mode"),
        CheckConstraint("format IN ('xlsx', 'csv', 'json', 'pdf')", name="format"),
        CheckConstraint("status IN ('pending', 'ready', 'failed')", name="status"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str]
    format: Mapped[str]
    status: Mapped[str]
    # Body of ``POST /api/exports`` as JSON: T-33 rebuilds the file from it in the background.
    params: Mapped[dict[str, Any]]
    rows_count: Mapped[int | None]
    file_name: Mapped[str | None]
    # Loaded only when the file is downloaded, never with the state of the export.
    content: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
    error: Mapped[str | None]
    expires_at: Mapped[datetime | None] = mapped_column(index=True)
