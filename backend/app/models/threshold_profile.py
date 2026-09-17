"""``threshold_profiles``: quality thresholds — global, of a district or of one line (ADR-004)."""

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ThresholdProfile(TimestampMixin, Base):
    """Thresholds a measurement is judged by: the most specific active profile of its line wins.

    Chain: the line, then the district of its school, then the global profile, which carries the
    base values of ТЗ п. 11 and is never switched off. A change never touches history: every
    measurement keeps its own ``thresholds_snapshot`` (ADR-004).
    """

    __tablename__ = "threshold_profiles"
    __table_args__ = (
        CheckConstraint("scope IN ('global', 'district', 'line')", name="scope"),
        CheckConstraint("(region_id IS NOT NULL) = (scope = 'district')", name="district_target"),
        CheckConstraint("(line_id IS NOT NULL) = (scope = 'line')", name="line_target"),
        # One profile per target; NULL targets of the other scopes do not collide.
        Index(
            "uq_threshold_profiles_scope",
            "scope",
            unique=True,
            postgresql_where=text("scope = 'global'"),
        ),
        UniqueConstraint("region_id"),
        UniqueConstraint("line_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    scope: Mapped[str]
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    line_id: Mapped[int | None] = mapped_column(ForeignKey("lines.id"))
    download_min_mbps: Mapped[float]
    upload_min_mbps: Mapped[float]
    ping_max_ms: Mapped[float]
    jitter_max_ms: Mapped[float]
    packet_loss_max_pct: Mapped[float]
    # One metric off the threshold by no more than this share → «Нестабильно» (T-18, ADR-004).
    unstable_deviation_pct: Mapped[float]
    is_active: Mapped[bool] = mapped_column(server_default=true())
