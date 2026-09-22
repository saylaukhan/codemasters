"""``incident_rules``: when a line gets an incident and when it counts as restored (ADR-007).

A rule watches one metric: N violations in a row or T minutes of violation open an incident,
M normal results in a row set ``restored_at`` (ТЗ п. 18). A ``global`` rule watches every
line; a ``school`` rule watches the lines of one school and replaces the global rule of the
same metric for them (T-85). The detection of T-40 reads the rules anew on every run, so an
edit in the admin panel applies to the next one. A rule is switched off with ``is_active``,
never deleted: its incidents refer to it.
"""

from sqlalchemy import CheckConstraint, ForeignKey, Identity, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin

# Codes of ``IncidentMetric`` in ``app/schemas/statuses.py``.
METRICS = (
    "download_mbps",
    "upload_mbps",
    "ping_ms",
    "jitter_ms",
    "packet_loss_pct",
    "no_connection",
)

# Codes of ``IncidentRuleScope`` in ``app/schemas/incident_rules.py``.
SCOPES = ("global", "school")


class IncidentRule(TimestampMixin, Base):
    """One rule of the incident detection; at least one of N and T is set."""

    __tablename__ = "incident_rules"
    __table_args__ = (
        CheckConstraint(one_of("metric", METRICS), name="metric"),
        CheckConstraint(one_of("scope", SCOPES), name="scope"),
        CheckConstraint("(school_id IS NOT NULL) = (scope = 'school')", name="school_target"),
        CheckConstraint(
            "consecutive_violations IS NOT NULL OR duration_min IS NOT NULL", name="condition"
        ),
        CheckConstraint("consecutive_violations >= 1", name="consecutive_violations"),
        CheckConstraint("duration_min >= 1", name="duration_min"),
        CheckConstraint("recovery_normal_count >= 1", name="recovery_normal_count"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str]
    metric: Mapped[str]
    # ``global`` — every line; ``school`` — the lines of ``school_id`` only (T-85).
    scope: Mapped[str] = mapped_column(server_default=text("'global'"))
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True)
    # N: violations in a row that open an incident.
    consecutive_violations: Mapped[int | None]
    # T: minutes from the first to the last violation of a run that open an incident.
    duration_min: Mapped[int | None]
    # M: normal results in a row after the last violation that set ``restored_at``.
    recovery_normal_count: Mapped[int]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
