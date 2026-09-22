"""``devices``: registered agents (ADR-005)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Device(TimestampMixin, Base):
    """Computer with an agent; its school and line come only from ``monitoring_point_id``."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'blocked')", name="status"),
        CheckConstraint("update_channel IN ('pilot', 'stable')", name="update_channel"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    device_uid: Mapped[str] = mapped_column(unique=True)
    monitoring_point_id: Mapped[int] = mapped_column(ForeignKey("monitoring_points.id"), index=True)
    hostname: Mapped[str | None]
    os: Mapped[str | None]
    agent_version: Mapped[str | None]
    # Hash of the device token; the token itself is never stored (ADR-005). ``sha256$…`` —
    # the token is 256 random bits, so a holding function buys nothing and costs the event
    # loop a request (``app/core/security.py``); an argon2 value here is a row written
    # before that and is replaced by the first request of its agent.
    token_hash: Mapped[str]
    registered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime | None]
    # Blocking keeps the device and its measurements (ТЗ п. 16, п. 20).
    status: Mapped[str] = mapped_column(server_default=text("'active'"))
    # Set by the admin panel: the agent sees it in its configuration and exchanges its token
    # with ``POST /api/agent/token``, which clears it (T-36).
    token_rotation_requested_at: Mapped[datetime | None]
    # Channel of the self-update: a device on ``pilot`` takes a release before the rest, which
    # wait for its promotion to ``stable`` (T-50).
    update_channel: Mapped[str] = mapped_column(server_default=text("'stable'"))
    # Set by the admin panel: the agent sees the moment in the answer of its heartbeat, measures
    # once outside its schedule and sends the result; the measurement clears it (T-79).
    measure_requested_at: Mapped[datetime | None]
