"""``lines``: internet lines of a school, main and reserve, with contract values (ADR-003)."""

from datetime import date, datetime
from ipaddress import IPv4Network, IPv6Network

from sqlalchemy import CheckConstraint, ForeignKey, Identity, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, CIDR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Line(TimestampMixin, Base):
    """Line of a provider at a school; measurements are evaluated per line (ТЗ п. 10)."""

    __tablename__ = "lines"
    __table_args__ = (
        CheckConstraint("status IN ('main', 'reserve', 'disabled')", name="status"),
        # Target of the composite foreign key from monitoring_points: a point cannot be bound
        # to a line of another school, so the school of a device is unambiguous (ADR-005).
        UniqueConstraint("id", "school_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    connection_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("connection_types.id"), index=True
    )
    # Line identifier assigned by the provider (account, circuit number).
    line_identifier: Mapped[str | None]
    # Contract values are compared with the fact separately from thresholds (ТЗ п. 14, ADR-004).
    contract_down_mbps: Mapped[float | None]
    contract_up_mbps: Mapped[float | None]
    contract_number: Mapped[str | None]
    contract_date: Mapped[date | None]
    started_at: Mapped[datetime | None]
    status: Mapped[str]
    # External IP ranges of the line: a measurement is attributed to the line by external_ip.
    ip_ranges: Mapped[list[IPv4Network | IPv6Network]] = mapped_column(
        ARRAY(CIDR), server_default=text("'{}'")
    )
