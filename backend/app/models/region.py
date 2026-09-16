"""``regions``: districts and cities of VKO with their boundaries (ADR-003)."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Region(TimestampMixin, Base):
    """District or city; ``code`` is part of the fallback School ID ``VKO-<code>-<number>``."""

    __tablename__ = "regions"
    __table_args__ = (Index("ix_regions_geom", "geom", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    # Boundary in WGS 84; loaded from the VKO GeoJSON by `make seed` (T-04).
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )
