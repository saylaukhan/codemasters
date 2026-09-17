"""``outages``: periods without connection, reported by agents and detected by the server."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Outage(TimestampMixin, Base):
    """Downtime of a line seen by a device; ``ended_at`` is empty while the outage lasts."""

    __tablename__ = "outages"
    __table_args__ = (
        # Idempotency key of a resent outage; it covers the foreign key too (ADR-006, T-16).
        Index("uq_outages_device_id_started_at", "device_id", "started_at", unique=True),
        Index("ix_outages_line_id_started_at", "line_id", "started_at"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="period"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"))
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
