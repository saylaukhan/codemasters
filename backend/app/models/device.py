"""``devices``: registered agents (ADR-005)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Device(TimestampMixin, Base):
    """Computer with an agent; its school and line come only from ``monitoring_point_id``."""

    __tablename__ = "devices"
    __table_args__ = (CheckConstraint("status IN ('active', 'blocked')", name="status"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    device_uid: Mapped[str] = mapped_column(unique=True)
    monitoring_point_id: Mapped[int] = mapped_column(ForeignKey("monitoring_points.id"), index=True)
    hostname: Mapped[str | None]
    os: Mapped[str | None]
    agent_version: Mapped[str | None]
    # argon2 hash of the device token; the token itself is never stored (ADR-005).
    token_hash: Mapped[str]
    registered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime | None]
    # Blocking keeps the device and its measurements (ТЗ п. 16, п. 20).
    status: Mapped[str] = mapped_column(server_default=text("'active'"))
