"""``calendar_events``: vacations, holidays and planned works that silence the monitoring (T-70)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CalendarEvent(TimestampMixin, Base):
    """Period the data of a school says nothing about its line (docs/design/README.md §6.5).

    Three kinds: ``vacation`` and ``holiday`` cover whole local days of ``settings.timezone`` —
    availability is not counted, incidents are not created and the silence of an agent is «Нет
    данных · каникулы» — and ``planned_works`` is a window of one provider, which additionally
    drops out of its score (ТЗ п. 14). The target is the whole oblast, one district or one
    school; RLS keeps a district inside its own rows (ADR-008).
    """

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("kind IN ('vacation', 'holiday', 'planned_works')", name="kind"),
        CheckConstraint("scope IN ('oblast', 'district', 'school')", name="scope"),
        CheckConstraint("(region_id IS NOT NULL) = (scope = 'district')", name="district_target"),
        CheckConstraint("(school_id IS NOT NULL) = (scope = 'school')", name="school_target"),
        CheckConstraint(
            "provider_id IS NULL OR kind = 'planned_works'", name="provider_of_planned_works"
        ),
        CheckConstraint("ends_at > starts_at", name="period"),
        # Every reader of the calendar asks for the events of a period.
        Index("ix_calendar_events_starts_at_ends_at", "starts_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    kind: Mapped[str]
    scope: Mapped[str]
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True)
    # Only for ``planned_works``: the window applies to the lines of this provider alone.
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), index=True)
    # Both ends are absolute moments; a whole local day is stored as its bounds in
    # ``settings.timezone``, so a vacation of the oblast ends when the local day ends (ADR-014).
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    title: Mapped[str]
    comment: Mapped[str | None]
