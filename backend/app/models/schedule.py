"""``schedules``: measurement slots of the agents — global, of a district or of a school."""

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Schedule(TimestampMixin, Base):
    """Schedule an agent measures by: the most specific active one of its school wins (T-17).

    Chain: the school, then its district, then the global schedule, which always exists and is
    never switched off (ТЗ п. 2, ADR-004). Slot times are local Asia/Almaty (ADR-014).
    """

    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("scope IN ('global', 'district', 'school')", name="scope"),
        CheckConstraint("(region_id IS NOT NULL) = (scope = 'district')", name="district_target"),
        CheckConstraint("(school_id IS NOT NULL) = (scope = 'school')", name="school_target"),
        # One schedule per target. The empty target columns of the other scopes are NULL, and
        # NULLs do not collide in a unique index, so one constraint per column is enough.
        Index(
            "uq_schedules_scope", "scope", unique=True, postgresql_where=text("scope = 'global'")
        ),
        UniqueConstraint("region_id"),
        UniqueConstraint("school_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    scope: Mapped[str]
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"))
    # 3–5 slots without an offset: [{"start": "08:30:00", "end": "09:00:00"}, …] (ADR-014).
    slots: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    # Zone the slot times are read in; it travels to the agent with them (ADR-014).
    timezone: Mapped[str] = mapped_column(server_default=text("'Asia/Almaty'"))
    # A switched-off schedule is skipped and the next one of the chain applies (T-37).
    is_active: Mapped[bool] = mapped_column(server_default=true())
