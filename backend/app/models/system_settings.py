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
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        # A year is the outer bound: further back a resend is not the queue of a school that
        # was offline but a rewrite of a period already reported (ТЗ п. 11, ADR-006).
        CheckConstraint(
            "agent_queue_retention_days BETWEEN 1 AND 365", name="agent_queue_retention_days"
        ),
    )

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
    # Sustained mismatch with the contract: more than this share of the measurements of the main
    # line below the contract speed over the window (ТЗ п. 14, T-29).
    contract_mismatch_threshold_pct: Mapped[float] = mapped_column(server_default=text("50"))
    contract_mismatch_window_days: Mapped[int] = mapped_column(server_default=text("7"))
    # An export of more rows than this, and every PDF, is built in the background (T-33).
    export_sync_max_rows: Mapped[int] = mapped_column(server_default=text("10000"))
    # Days a built export file is kept before it answers 404 (ТЗ п. 9, T-30, T-33).
    export_retention_days: Mapped[int] = mapped_column(server_default=text("7"))
    # Days an agent installation code stays valid (ADR-005, T-36).
    enrollment_code_ttl_days: Mapped[int] = mapped_column(server_default=text("7"))
    # A resolved incident is closed after this many hours (ADR-007, T-40).
    incident_auto_close_hours: Mapped[int] = mapped_column(server_default=text("24"))
    # Windows of «Требуют внимания» of the main screen (T-60, docs/design/README.md §4.1, §6.3):
    # an open incident left without a responsible person for this long, and an appeal the
    # provider has not moved for this long, ask for a person.
    attention_incident_unassigned_hours: Mapped[int] = mapped_column(server_default=text("24"))
    attention_appeal_no_answer_hours: Mapped[int] = mapped_column(server_default=text("48"))
    # Days an agent keeps a measurement in its SQLite queue, and the depth of history the server
    # accepts from it: the agent gets it from GET /api/agent/config, nothing is hard-coded on
    # either side (ТЗ п. 11, п. 20; ADR-004, ADR-006).
    agent_queue_retention_days: Mapped[int] = mapped_column(server_default=text("30"))
    # Silence of an installed agent that long puts its school into «молчит» of «Внедрение»
    # (T-69, docs/design/README.md §6.4); «на связи» is decided by ``offline_after_s``.
    rollout_silent_days: Mapped[int] = mapped_column(server_default=text("7"))
    # How long a «Забыли пароль?» link stays valid, and the contact the sign-in screen shows
    # instead of the link on an installation without SMTP (T-65, docs/design/README.md §4.6).
    password_reset_ttl_minutes: Mapped[int] = mapped_column(server_default=text("30"))
    support_contact: Mapped[str] = mapped_column(server_default=text("''"))
