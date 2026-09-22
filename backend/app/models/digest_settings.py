"""``digest_settings``: one weekly mailing of the digest of a scope (T-67, §6.2 of the design).

The scope is the whole oblast or one district; ``weekday`` (1 — Monday) and ``hour`` are read in
``settings.timezone``, so the schedule of the mailing is a setting and not a constant of the code
(ТЗ п. 11, п. 20; ADR-004). ``last_sent_at`` is stamped by the beat task of T-67 and is what
keeps one issue from going twice inside its window, a worker restart included.

The table is administration-only, like ``threshold_profiles`` and ``schedules``: every endpoint
requires ``settings:manage``, which only Область and Администратор have, so the row carries no
RLS policy (ADR-008).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit_log import one_of
from app.models.base import Base, TimestampMixin

# Codes of ``DigestScope`` in ``app/schemas/digests.py``.
SCOPES = ("oblast", "region")


class DigestSettings(TimestampMixin, Base):
    """Mailing of the digest: whose numbers it carries, when it leaves and where it goes."""

    __tablename__ = "digest_settings"
    __table_args__ = (
        CheckConstraint(one_of("scope", SCOPES), name="scope"),
        CheckConstraint("(region_id IS NOT NULL) = (scope = 'region')", name="region_target"),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday"),
        CheckConstraint("hour BETWEEN 0 AND 23", name="hour"),
        # The beat task asks once an hour for the switched-on rows of this weekday and hour.
        Index(
            "ix_digest_settings_weekday_hour",
            "weekday",
            "hour",
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    scope: Mapped[str]
    # Empty means the whole oblast (``scope = 'oblast'``).
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    # 1 — Monday … 7 — Sunday, and the hour 0–23, both in ``settings.timezone`` (ADR-014).
    weekday: Mapped[int]
    hour: Mapped[int]
    # E-mail addresses of the mailing; contacts of ТЗ п. 15, never a secret.
    recipients: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    telegram_chat_id: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(server_default=true())
    # When the mailing last left the server; empty while it never did.
    last_sent_at: Mapped[datetime | None]
