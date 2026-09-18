"""``schools``: monitored schools, the root of the data chain (ADR-003)."""

from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ForeignKey, Identity, Index, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class School(TimestampMixin, Base):
    """School; ``school_code`` is the School ID from the customer (ТЗ п. 12)."""

    __tablename__ = "schools"
    __table_args__ = (Index("ix_schools_geom", "geom", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    school_code: Mapped[str] = mapped_column(unique=True)
    full_name: Mapped[str]
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    address: Mapped[str | None]
    # Map point in WGS 84 (ТЗ п. 13).
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    # Hours downtime counts in, ``WorkingHours`` of the API; NULL — the admin default (ADR-014).
    working_hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Deactivation instead of deletion: measurements and incidents stay (ТЗ п. 20).
    is_active: Mapped[bool] = mapped_column(server_default=true())
