"""Columns shared by the continuous aggregates of ``measurements`` (T-19, plan.md §5).

``m_hourly`` and ``m_daily`` are TimescaleDB views, not tables: a migration creates them and
nothing writes to them, so the models here are for reading only. ``info`` marks them for
``alembic/env.py``, which would otherwise see a model without a table and try to create one.
"""

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

# Marker of a continuous aggregate; autogenerate skips every model that carries it.
CONTINUOUS_AGGREGATE = {"info": {"continuous_aggregate": True}}


class MeasurementRollup:
    """One bucket of one device on one line: averages, extremes and how many were bad.

    ``bucket`` is the start of the hour or of the day in Asia/Almaty, stored as UTC like every
    other moment (ADR-014). Wi-Fi measurements are not in these numbers: they measure the air,
    not the line (ADR-012). Empty averages mean the bucket holds only measurements without a
    connection — there was nothing to average.
    """

    __table_args__ = CONTINUOUS_AGGREGATE

    bucket: Mapped[datetime] = mapped_column(primary_key=True)
    line_id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(primary_key=True)
    measurements_count: Mapped[int]
    # Measurements that were not «Норма»: «Нестабильно», «Критично» or «Нет соединения».
    problem_count: Mapped[int]
    # Measurements slower than the contract promises; «нечего сравнивать» is not one (ТЗ п. 14).
    below_contract_count: Mapped[int]
    avg_download_mbps: Mapped[float | None]
    min_download_mbps: Mapped[float | None]
    max_download_mbps: Mapped[float | None]
    avg_upload_mbps: Mapped[float | None]
    min_upload_mbps: Mapped[float | None]
    max_upload_mbps: Mapped[float | None]
    avg_ping_ms: Mapped[float | None]
    min_ping_ms: Mapped[float | None]
    max_ping_ms: Mapped[float | None]
    avg_jitter_ms: Mapped[float | None]
    min_jitter_ms: Mapped[float | None]
    max_jitter_ms: Mapped[float | None]
    avg_packet_loss_pct: Mapped[float | None]
    min_packet_loss_pct: Mapped[float | None]
    max_packet_loss_pct: Mapped[float | None]
