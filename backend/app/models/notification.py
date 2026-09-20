"""``notifications``: one notification of one incident for one panel user (ТЗ п. 18, ADR-007).

A row is the panel channel itself: the bell reads the unread ones, the stream of T-42 hands them
over without a page reload. Recipients are computed from the scope of ADR-008, so a user of
another district never gets a row of the incident. The text is written when the row is created:
an incident that changes later keeps the wording the person was notified with. Rows are never
deleted; reading one only sets ``read_at``.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin

# Codes of ``NotificationKind`` in ``app/schemas/notifications.py``.
KINDS = ("incident_opened", "incident_status_changed", "incident_restored")


class Notification(TimestampMixin, Base):
    """Notification of a user about an incident: what happened, when, and whether it was read."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(one_of("kind", KINDS), name="kind"),
        # The bell and the panel read one user newest first; the unread part gets its own index
        # because the counter of the bell asks for it on every poll.
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index(
            "ix_notifications_user_id_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[str]
    # Russian, sentence case, as the panel shows them (ADR-013): «Новый инцидент INC-2026-000123».
    title: Mapped[str]
    body: Mapped[str]
    read_at: Mapped[datetime | None]
