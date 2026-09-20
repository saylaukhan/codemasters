"""``notification_log``: every attempt to deliver a notification, successful or not (ТЗ п. 18).

One row per channel per notification: the panel row itself, the message to Telegram, the letter
by SMTP. A channel that is not configured — no bot token, no SMTP host, a user without a chat id
— is written as ``skipped`` with the reason, so the journal explains a silence instead of hiding
it. Rows are only added: the panel role may not update them (migration of T-42), like
``audit_log`` and ``incident_events``. Tokens and passwords never get here; ``target`` holds the
address the message went to, which is a contact of ТЗ п. 15, not a secret.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base

# Codes of ``NotificationChannel`` and ``NotificationResult`` in ``app/schemas/notifications.py``.
CHANNELS = ("panel", "telegram", "email")
RESULTS = ("sent", "failed", "skipped")


class NotificationLog(Base):
    """One delivery attempt: which notification, which channel, what came of it."""

    __tablename__ = "notification_log"
    __table_args__ = (
        CheckConstraint(one_of("channel", CHANNELS), name="channel"),
        CheckConstraint(one_of("result", RESULTS), name="result"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    channel: Mapped[str]
    result: Mapped[str]
    # Where it went: the e-mail of the user, his Telegram chat, «панель» for the row itself.
    target: Mapped[str | None]
    # Why it failed or was skipped; empty for a delivered message.
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
