"""``appeal_events``: the history of an appeal — the sending, status changes and comments.

Rows are only added: the panel role may not update them (migration of T-48), so the history is
what happened (ТЗ п. 17, ADR-007). Unlike ``incident_events``, every row here has an author:
nothing moves an appeal by itself.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base
from app.models.incident import STATUSES

# Codes of ``AppealEventKind`` in ``app/schemas/appeals.py``.
KINDS = ("sent", "status_change", "comment")


class AppealEvent(Base):
    """One entry of the appeal history."""

    __tablename__ = "appeal_events"
    __table_args__ = (
        CheckConstraint(one_of("kind", KINDS), name="kind"),
        CheckConstraint(one_of("from_status", STATUSES), name="from_status"),
        CheckConstraint(one_of("to_status", STATUSES), name="to_status"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    appeal_id: Mapped[int] = mapped_column(ForeignKey("appeals.id"), index=True)
    kind: Mapped[str]
    from_status: Mapped[str | None]
    to_status: Mapped[str | None]
    comment: Mapped[str | None]
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
