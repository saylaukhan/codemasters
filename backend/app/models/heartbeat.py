"""``heartbeats``: "agent is alive" signals, a TimescaleDB hypertable on ``ts``."""

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Heartbeat(Base):
    """Heartbeat of a device; gaps in working hours count as downtime (ADR-014)."""

    __tablename__ = "heartbeats"

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(primary_key=True)
    online: Mapped[bool]
