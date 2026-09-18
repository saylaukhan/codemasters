"""``incident_events``: the history of an incident — created, status changes, comments, restored.

Rows are only added: the panel role may not update them (migration of T-40), so the history is
what happened, not what someone wished had happened (ТЗ п. 19, ADR-007). An event without an
author is an action of the system: the detection or the auto-close.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base
from app.models.incident import STATUSES

# Codes of ``IncidentEventKind`` in ``app/schemas/incidents.py``.
KINDS = ("created", "status_change", "comment", "restored")


class IncidentEvent(Base):
    """One entry of the incident history."""

    __tablename__ = "incident_events"
    __table_args__ = (
        CheckConstraint(one_of("kind", KINDS), name="kind"),
        CheckConstraint(one_of("from_status", STATUSES), name="from_status"),
        CheckConstraint(one_of("to_status", STATUSES), name="to_status"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[str]
    from_status: Mapped[str | None]
    to_status: Mapped[str | None]
    comment: Mapped[str | None]
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
