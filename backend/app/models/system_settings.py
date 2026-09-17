"""``settings``: the single row of system-wide values changed in the admin panel (T-37).

``make seed`` stores the initial values from the environment; after that the database is the
source of truth, and agents get their part from ``GET /api/agent/config`` (T-17, ADR-012).
T-05 adds the measurement servers, T-17 the intervals of the agent, T-16 the rules the status
of a school and its availability are counted by; the other values of ``SettingsDetail`` arrive
with the tasks that use them.
"""

from typing import Any

from sqlalchemy import CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemSettings(TimestampMixin, Base):
    """System settings; the table holds at most one row, ``id = 1``."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, server_default=text("1"))
    # Main measurement server and the ndt7 fallback; NULL means no fallback (ADR-012).
    librespeed_url: Mapped[str]
    ndt7_url: Mapped[str | None]
    # How often an agent reports it is alive and asks for its configuration again (T-17).
    heartbeat_interval_s: Mapped[int] = mapped_column(server_default=text("300"))
    config_refresh_interval_s: Mapped[int] = mapped_column(server_default=text("900"))
    # Zone the working hours and the reports are read in; storage stays UTC (ADR-014).
    timezone: Mapped[str] = mapped_column(server_default=text("'Asia/Almaty'"))
    # Silence longer than this is «Нет соединения» in working hours, «Нет данных» outside them.
    offline_after_s: Mapped[int] = mapped_column(server_default=text("900"))
    # How many last measurements of the main line give the status of a school (ADR-004).
    school_status_measurements_count: Mapped[int] = mapped_column(server_default=text("3"))
    # Working hours a school is created with; downtime counts only inside them (ADR-014, T-37).
    default_working_hours: Mapped[dict[str, Any]] = mapped_column(
        server_default=text(
            """'{"weekdays": ["mon", "tue", "wed", "thu", "fri", "sat"], """
            """"start": "08:00:00", "end": "18:00:00"}'::jsonb"""
        )
    )
    # Availability of ТЗ п. 11 a school is expected to stay above.
    availability_min_pct: Mapped[float] = mapped_column(server_default=text("99"))
