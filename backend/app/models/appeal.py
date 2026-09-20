"""``appeals``: letters to providers, sent from the panel (ТЗ п. 17, ADR-011).

A draft is nothing: it is built on every request and stored nowhere (T-47). A row appears here
only on «Отправить», and only then the number ``ОБР-<year>-<six digits>`` is taken from
``appeal_number_seq`` — never reused, never reset. The facts the letter argues by are frozen in
``context``: the appeal keeps what was true at the sending, not what the measurements say today
(ТЗ п. 17). The school and the provider are copied from the line for the same reason the
incident copies them: a later rebinding of the line must not move the history.

``delivery_status`` is the fate of the letter, not of the appeal: an installation without SMTP
or a provider without ``appeals_email`` still gets an appeal with a number and a PDF, marked
``not_sent`` («Решения по умолчанию», ADR-011). Rows are never deleted; every change of status
is an ``appeal_events`` row.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin
from app.models.incident import STATUSES

# Codes of ``AppealDeliveryStatus`` in ``app/schemas/appeals.py``.
DELIVERY_STATUSES = ("sent", "not_sent")


class Appeal(TimestampMixin, Base):
    """One sent appeal: its number, text, the facts at the sending and the fate of the letter."""

    __tablename__ = "appeals"
    __table_args__ = (
        CheckConstraint(one_of("status", STATUSES), name="status"),
        CheckConstraint(one_of("delivery_status", DELIVERY_STATUSES), name="delivery_status"),
        Index("ix_appeals_sent_at", "sent_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # ``ОБР-<year>-<six digits>`` from the sequence ``appeal_number_seq``.
    number: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str]
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"), index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    subject: Mapped[str]
    # The letter the person sent, in Markdown: what the model wrote and he edited (ADR-011).
    text: Mapped[str]
    user_comment: Mapped[str | None]
    # ``AppealContext`` as JSON: the facts of the appeal at the moment of the sending.
    context: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recipient_email: Mapped[str | None]
    delivery_status: Mapped[str]
    # Why the letter did not go: no SMTP, no address or the answer of the server.
    delivery_error: Mapped[str | None]
    sent_at: Mapped[datetime]
    # Loaded only when the PDF is downloaded, never with the card of the appeal.
    pdf: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
