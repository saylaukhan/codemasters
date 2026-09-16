"""Requests and responses of the admin references (plan.md §5, §10 «Админка», ТЗ п. 14, п. 20).

Districts and cities, providers and connection types are referenced by schools and lines, so
they are edited but never deleted. In a PATCH body an absent field stays unchanged, ``null``
clears a nullable field, and ``null`` for any other field is a 422.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page

# Region code goes into the fallback School ID ``VKO-<code>-<number>``: Latin capitals and digits.
REGION_CODE_PATTERN = r"^[A-Z0-9]+$"
CONNECTION_TYPE_CODE_PATTERN = r"^[a-z][a-z0-9_]*$"

# Position of RFC 7946 §3.1.1 without altitude: [longitude, latitude] in WGS 84.
LonLat = tuple[Annotated[float, Field(ge=-180, le=180)], Annotated[float, Field(ge=-90, le=90)]]
LinearRing = Annotated[list[LonLat], Field(min_length=4)]


class GeoJsonMultiPolygon(BaseModel):
    """GeoJSON MultiPolygon geometry (RFC 7946 §3.1.7) in WGS 84: the boundary of a region."""

    type: Literal["MultiPolygon"]
    coordinates: list[Annotated[list[LinearRing], Field(min_length=1)]] = Field(
        min_length=1,
        description="Полигоны → кольца (первое — внешняя граница, остальные — вырезы) → "
        "точки [долгота, широта]; кольцо замкнуто: первая точка равна последней",
        examples=[[[[[82.5, 49.9], [82.7, 49.9], [82.7, 50.0], [82.5, 49.9]]]]],
    )

    @field_validator("coordinates")
    @classmethod
    def check_rings_closed(cls, polygons: list[list[list[LonLat]]]) -> list[list[list[LonLat]]]:
        if any(ring[0] != ring[-1] for polygon in polygons for ring in polygon):
            raise ValueError("кольцо полигона должно быть замкнуто: первая точка равна последней")
        return polygons


class ProviderCreate(BaseModel):
    """New internet service provider (ТЗ п. 14, п. 20)."""

    name: str = Field(min_length=1, max_length=255, examples=["ТОО «Провайдер ВКО»"])
    appeals_email: str | None = Field(
        default=None,
        max_length=254,
        examples=["support@example.kz"],
        description="Служебный адрес поставщика для обращений (T-48); не личный e-mail",
    )


class ProviderUpdate(BaseModel):
    """Changes of a provider."""

    name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    appeals_email: str | None = Field(default=None, max_length=254)

    @field_validator("name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class ProviderDetail(BaseModel):
    """Internet service provider; the scope of the Provider role (ADR-008)."""

    id: int
    name: str
    appeals_email: str | None = Field(description="Служебный адрес поставщика для обращений")


class ProviderDetailPage(Page[ProviderDetail]):
    """Page of the providers, by name."""


class RegionCreate(BaseModel):
    """New district or city of VKO (ТЗ п. 20); the boundary is usually loaded by T-04."""

    code: str = Field(
        min_length=1,
        max_length=16,
        pattern=REGION_CODE_PATTERN,
        examples=["UKG"],
        description="Латинские заглавные и цифры; часть School ID VKO-<код>-<номер>",
    )
    name: str = Field(min_length=1, max_length=255, examples=["Усть-Каменогорск"])
    boundary: GeoJsonMultiPolygon | None = None


class RegionUpdate(BaseModel):
    """Changes of a region; ``boundary = null`` removes the boundary."""

    code: (
        Annotated[str, Field(min_length=1, max_length=16, pattern=REGION_CODE_PATTERN)]
        | SkipJsonSchema[None]
    ) = None
    name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    boundary: GeoJsonMultiPolygon | None = None

    @field_validator("code", "name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class RegionListItem(BaseModel):
    """Row of the region reference; the boundary itself is not listed."""

    id: int
    code: str
    name: str
    has_boundary: bool = Field(description="Граница района или города загружена")


class RegionListItemPage(Page[RegionListItem]):
    """Page of the regions, by name."""


class RegionDetail(BaseModel):
    """District or city of VKO with its boundary."""

    id: int
    code: str = Field(description="Часть School ID VKO-<код>-<номер>")
    name: str
    boundary: GeoJsonMultiPolygon | None = Field(description="null — граница не загружена")


class ConnectionTypeCreate(BaseModel):
    """New line technology (ТЗ п. 14, п. 20)."""

    code: str = Field(
        min_length=1,
        max_length=32,
        pattern=CONNECTION_TYPE_CODE_PATTERN,
        examples=["fiber"],
        description="Постоянный код: строчная латиница, цифры, «_»",
    )
    name: str = Field(min_length=1, max_length=255, examples=["Оптоволокно"])


class ConnectionTypeUpdate(BaseModel):
    """Changes of a connection type."""

    code: (
        Annotated[str, Field(min_length=1, max_length=32, pattern=CONNECTION_TYPE_CODE_PATTERN)]
        | SkipJsonSchema[None]
    ) = None
    name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None

    @field_validator("code", "name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class ConnectionTypeDetail(BaseModel):
    """Line technology: fiber, ADSL, radio and so on."""

    id: int
    code: str
    name: str


class ConnectionTypeDetailPage(Page[ConnectionTypeDetail]):
    """Page of the connection types, by name."""
