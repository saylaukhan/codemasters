"""``incidents``: sustained problems of a line, opened by a rule or by a person (ТЗ п. 19).

The detection of T-40 keeps one open incident per line and rule: an incident is open for it
until ``restored_at`` is set or the incident is resolved or closed, and a partial unique index
holds that under concurrency. A manual incident has no rule (T-41). The school and the provider
are copied from the line when the incident is opened, so a later rebinding of the line does not
move the history. Rows are never deleted; every change of status is an ``incident_events`` row.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin

# Codes of ``IncidentStatus`` in ``app/schemas/statuses.py``, in the order of ТЗ п. 19.
STATUSES = ("new", "sent_to_provider", "in_progress", "awaiting_info", "resolved", "closed")

# Open for the detection: neither restored nor resolved or closed by a person (ADR-007).
OPEN_FOR_DETECTION = (
    "rule_id IS NOT NULL AND restored_at IS NULL AND status NOT IN ('resolved', 'closed')"
)


class Incident(TimestampMixin, Base):
    """One incident of a line: its number, status, basis and the moments of its life."""

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(one_of("status", STATUSES), name="status"),
        Index(
            "uq_incidents_line_id_rule_id_open",
            "line_id",
            "rule_id",
            unique=True,
            postgresql_where=text(OPEN_FOR_DETECTION),
        ),
        Index("ix_incidents_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # ``INC-<year>-<six digits>`` from the sequence ``incident_number_seq``.
    number: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str]
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("incident_rules.id"), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"), index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    # ``IncidentBasisMetric`` items: the violating value next to its threshold (ТЗ п. 19).
    basis_metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    description: Mapped[str | None]
    # First violation of the run that opened the incident.
    started_at: Mapped[datetime]
    # Latest violation seen while the incident is open; empty for a manual incident.
    last_violation_at: Mapped[datetime | None]
    sent_to_provider_at: Mapped[datetime | None]
    # First normal result of the M in a row that restored the line.
    restored_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
