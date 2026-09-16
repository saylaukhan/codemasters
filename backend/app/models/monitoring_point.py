"""``monitoring_points``: places at a school where agents measure a line (ТЗ п. 10)."""

from sqlalchemy import ForeignKeyConstraint, Identity, Index, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MonitoringPoint(TimestampMixin, Base):
    """Monitoring point bound to one line of the same school; ``is_primary`` marks the main one."""

    __tablename__ = "monitoring_points"
    __table_args__ = (
        # The line must belong to the same school as the point (see Line.__table_args__).
        ForeignKeyConstraint(["line_id", "school_id"], ["lines.id", "lines.school_id"]),
        Index("ix_monitoring_points_line_id_school_id", "line_id", "school_id"),
        # At most one primary point per school.
        Index(
            "uq_monitoring_points_school_id_is_primary",
            "school_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    line_id: Mapped[int]
    name: Mapped[str]
    room: Mapped[str | None]
    is_primary: Mapped[bool] = mapped_column(server_default=false())
