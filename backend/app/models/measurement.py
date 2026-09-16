"""``measurements``: raw measurement results, a TimescaleDB hypertable on ``measured_at``.

TimescaleDB requires every unique index of a hypertable to include the partitioning column, so
the primary key is ``(id, measured_at)`` and idempotency is enforced on
``(measurement_uuid, measured_at)``: the agent sets both at measurement time and resends them
unchanged (ADR-006).
"""

import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Measurement(Base):
    """One measurement of a device on a line: raw values plus the server-side evaluation."""

    __tablename__ = "measurements"
    __table_args__ = (
        Index("uq_measurements_measurement_uuid", "measurement_uuid", "measured_at", unique=True),
        Index("ix_measurements_measured_at", "measured_at"),
        Index("ix_measurements_device_id_measured_at", "device_id", "measured_at"),
        Index("ix_measurements_line_id_measured_at", "line_id", "measured_at"),
        CheckConstraint("connection_status IN ('online', 'offline')", name="connection_status"),
        CheckConstraint(
            "quality_status IN ('normal', 'unstable', 'critical', 'offline')",
            name="quality_status",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Moment of the measurement on the computer, sent by the agent (ADR-014).
    measured_at: Mapped[datetime] = mapped_column(primary_key=True)
    measurement_uuid: Mapped[uuid.UUID]
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"))
    # Set by the server; the gap to measured_at is the time spent in the offline queue.
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())
    download_mbps: Mapped[float | None]
    upload_mbps: Mapped[float | None]
    ping_ms: Mapped[float | None]
    jitter_ms: Mapped[float | None]
    packet_loss_pct: Mapped[float | None]
    connection_status: Mapped[str]
    duration_s: Mapped[float | None]
    external_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    server: Mapped[str | None]
    iface_type: Mapped[str | None]
    agent_version: Mapped[str | None]
    # Evaluation on receipt (T-18): thresholds applied, quality status, contract check (ADR-004).
    thresholds_snapshot: Mapped[dict[str, Any] | None]
    quality_status: Mapped[str | None]
    contract_ok: Mapped[bool | None]
