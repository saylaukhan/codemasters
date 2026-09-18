"""Schools and district boundaries on the VKO map as GeoJSON (RFC 7946, ТЗ п. 13, T-22, T-23).

``properties`` are flat, in the order of the popover fields of ТЗ п. 13: MapLibre turns nested
objects of feature properties into strings. No personal data here (ADR-003).
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.references import GeoJsonMultiPolygon
from app.schemas.statuses import SchoolStatus


class GeoJsonPoint(BaseModel):
    """GeoJSON Point geometry (RFC 7946 §3.1.2) in WGS 84."""

    type: Literal["Point"]
    coordinates: tuple[
        Annotated[float, Field(ge=-180, le=180)],
        Annotated[float, Field(ge=-90, le=90)],
    ] = Field(description="[долгота, широта], WGS 84", examples=[[82.6286, 49.9483]])


class SchoolMapProperties(BaseModel):
    """Popover of a school (T-23); values below a threshold are highlighted by the panel.

    Line fields and metrics refer to the main line (``lines.status = main``); metrics exclude
    Wi-Fi (ADR-012).
    """

    school_code: str = Field(description="School ID")
    full_name: str = Field(description="Полное наименование школы")
    region_name: str = Field(description="Район/город")
    provider_name: str | None
    connection_type_name: str | None
    contract_down_mbps: float | None = Field(description="Договорная скорость Download")
    contract_up_mbps: float | None = Field(description="Договорная скорость Upload")
    status: SchoolStatus
    download_mbps: float | None
    upload_mbps: float | None
    ping_ms: float | None
    last_measured_at: datetime | None = Field(description="Время последнего замера в периоде")
    download_min_mbps: float | None = Field(description="Порог Download из снимка этого замера")
    upload_min_mbps: float | None = Field(description="Порог Upload из снимка этого замера")
    ping_max_ms: float | None = Field(description="Порог Ping из снимка этого замера")


class SchoolMapFeature(BaseModel):
    """One school; ``id`` is ``schools.id``, the target of the school card."""

    type: Literal["Feature"]
    id: int
    geometry: GeoJsonPoint | None = Field(description="null — у школы нет координат")
    properties: SchoolMapProperties


class SchoolMapFeatureCollection(BaseModel):
    """Every active school matching the filters: the map is a whole set, not a paginated list."""

    type: Literal["FeatureCollection"]
    features: list[SchoolMapFeature]


class RegionMapProperties(BaseModel):
    """District or city of VKO under its boundary."""

    code: str
    name: str = Field(description="Район/город")


class RegionMapFeature(BaseModel):
    """Boundary of one district or city; ``id`` is ``regions.id``, the value of ``region_id``."""

    type: Literal["Feature"]
    id: int
    geometry: GeoJsonMultiPolygon | None = Field(description="null — граница не загружена")
    properties: RegionMapProperties


class RegionMapFeatureCollection(BaseModel):
    """Every district and city of VKO: the boundaries are a reference, not a scoped record."""

    type: Literal["FeatureCollection"]
    features: list[RegionMapFeature]


class MapFilterOption(BaseModel):
    """One value of a filter: the id goes into the query, the name into the panel."""

    id: int
    name: str


class MapFilterOptions(BaseModel):
    """Values of the filters of the map and the overview, limited to the user's scope (ADR-008).

    Districts of the visible schools; providers and connection types of the visible lines.
    """

    regions: list[MapFilterOption]
    providers: list[MapFilterOption]
    connection_types: list[MapFilterOption]
