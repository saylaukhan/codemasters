"""Admin references and schools (T-34, ТЗ п. 14, п. 20): create and edit, never delete.

Districts and cities, providers and connection types are referenced by schools and lines; a
school is deactivated with ``is_active`` and keeps its history. A code or a name taken by
another row is a 409 with a type of its own, an unknown region is a 422 on ``region_id``.
``apply_changes`` returns the changed fields for the audit record (``describe_action``); the
middleware writes the record itself after the answer (ADR-008).

Queries run in the session of the request: schools under RLS, the references without it.
Only Область and Администратор may call these endpoints, and their scope is the whole oblast.
"""

import json
from collections.abc import Sequence
from typing import Any

from fastapi.exceptions import RequestValidationError
from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import ConnectionType, Provider, Region, School, SystemSettings
from app.schemas.references import (
    ConnectionTypeCreate,
    ConnectionTypeDetail,
    ConnectionTypeDetailPage,
    ConnectionTypeUpdate,
    GeoJsonMultiPolygon,
    ProviderCreate,
    ProviderDetail,
    ProviderDetailPage,
    ProviderUpdate,
    RegionCreate,
    RegionDetail,
    RegionListItem,
    RegionListItemPage,
    RegionUpdate,
)
from app.schemas.schools import GeoPoint, SchoolCreate, SchoolUpdate
from app.services.school_card import school_not_found

type Changes = dict[str, dict[str, Any]]


def invalid_field(field: str, message: str) -> RequestValidationError:
    return RequestValidationError(
        [{"type": "value_error", "loc": ("body", field), "msg": message, "ctx": {"error": message}}]
    )


def matching(q: str | None, *columns: InstrumentedAttribute[str]) -> list[ColumnElement[bool]]:
    """Filter of the ``q`` search: a part of any of ``columns``, case-insensitive."""
    if not q:
        return []
    pattern = f"%{q}%"
    return [or_(*(column.ilike(pattern) for column in columns))]


async def page_of(
    session: AsyncSession, query: Select[Any], params: PageParams
) -> tuple[Sequence[Any], int]:
    """Rows of the requested page and the number of all rows of ``query``."""
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (await session.execute(query.limit(params.page_size).offset(params.offset))).all()
    return rows, total


async def is_taken(
    session: AsyncSession, column: InstrumentedAttribute[str], value: str, own_id: int | None
) -> bool:
    """Another row than ``own_id`` already has ``value`` in the unique ``column``."""
    model: Any = column.class_
    query = select(model.id).where(column == value)
    if own_id is not None:
        query = query.where(model.id != own_id)
    return await session.scalar(query.limit(1)) is not None


def apply_changes(row: object, updates: dict[str, Any]) -> Changes:
    """Set ``updates`` on ``row``; the fields that changed as ``{field: {"old", "new"}}``."""
    changes: Changes = {}
    for name, value in updates.items():
        old = getattr(row, name)
        if old != value:
            setattr(row, name, value)
            changes[name] = {"old": old, "new": value}
    return changes


# --- Providers -----------------------------------------------------------------------------


def provider_name_taken() -> ApiError:
    return ApiError(409, "provider_name_taken", "Поставщик с таким названием уже есть")


def provider_detail(provider: Provider) -> ProviderDetail:
    return ProviderDetail(id=provider.id, name=provider.name, appeals_email=provider.appeals_email)


async def provider_list(
    session: AsyncSession, params: PageParams, q: str | None
) -> ProviderDetailPage:
    query = select(Provider).where(*matching(q, Provider.name)).order_by(Provider.name, Provider.id)
    rows, total = await page_of(session, query, params)
    return ProviderDetailPage(
        items=[provider_detail(row.Provider) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_provider(session: AsyncSession, body: ProviderCreate) -> ProviderDetail:
    if await is_taken(session, Provider.name, body.name, None):
        raise provider_name_taken()
    provider = Provider(name=body.name, appeals_email=body.appeals_email)
    session.add(provider)
    await session.commit()
    return provider_detail(provider)


async def update_provider(
    session: AsyncSession, provider_id: int, body: ProviderUpdate
) -> tuple[ProviderDetail, Changes]:
    provider = await session.get(Provider, provider_id)
    if provider is None:
        raise ApiError(404, "not_found", "Поставщик не найден")
    if body.name is not None and await is_taken(session, Provider.name, body.name, provider_id):
        raise provider_name_taken()
    changes = apply_changes(provider, body.model_dump(exclude_unset=True))
    await session.commit()
    return provider_detail(provider), changes


# --- Districts and cities ------------------------------------------------------------------


def region_code_taken() -> ApiError:
    return ApiError(409, "region_code_taken", "Район или город с таким кодом уже есть")


def boundary_geom(boundary: GeoJsonMultiPolygon | None) -> Any:
    """PostGIS geometry of a GeoJSON boundary; GeoJSON is WGS 84, SRID 4326."""
    if boundary is None:
        return None
    return func.ST_GeomFromGeoJSON(json.dumps(boundary.model_dump()))


async def region_list(
    session: AsyncSession, params: PageParams, q: str | None
) -> RegionListItemPage:
    query = (
        select(Region.id, Region.code, Region.name, Region.geom.is_not(None).label("has_boundary"))
        .where(*matching(q, Region.name, Region.code))
        .order_by(Region.name, Region.id)
    )
    rows, total = await page_of(session, query, params)
    return RegionListItemPage(
        items=[RegionListItem.model_validate(row._asdict()) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def region_detail(session: AsyncSession, region_id: int) -> RegionDetail:
    row = (
        await session.execute(
            select(Region.id, Region.code, Region.name, func.ST_AsGeoJSON(Region.geom)).where(
                Region.id == region_id
            )
        )
    ).one()
    _, code, name, geometry = row
    return RegionDetail.model_validate(
        {
            "id": region_id,
            "code": code,
            "name": name,
            "boundary": json.loads(geometry) if geometry else None,
        }
    )


async def create_region(session: AsyncSession, body: RegionCreate) -> RegionDetail:
    if await is_taken(session, Region.code, body.code, None):
        raise region_code_taken()
    region = Region(code=body.code, name=body.name, geom=boundary_geom(body.boundary))
    session.add(region)
    await session.commit()
    return await region_detail(session, region.id)


async def update_region(
    session: AsyncSession, region_id: int, body: RegionUpdate
) -> tuple[RegionDetail, Changes]:
    region = await session.get(Region, region_id)
    if region is None:
        raise ApiError(404, "not_found", "Район или город не найден")
    if body.code is not None and await is_taken(session, Region.code, body.code, region_id):
        raise region_code_taken()
    updates = body.model_dump(exclude_unset=True, exclude={"boundary"})
    changes = apply_changes(region, updates)
    if "boundary" in body.model_fields_set:
        # The geometry itself is too large for the log: only whether there is one.
        changes["has_boundary"] = {"old": region.geom is not None, "new": body.boundary is not None}
        region.geom = boundary_geom(body.boundary)
    await session.commit()
    return await region_detail(session, region_id), changes


# --- Connection types ----------------------------------------------------------------------


def connection_type_code_taken() -> ApiError:
    return ApiError(409, "connection_type_code_taken", "Тип подключения с таким кодом уже есть")


def connection_type_detail(connection_type: ConnectionType) -> ConnectionTypeDetail:
    return ConnectionTypeDetail(
        id=connection_type.id, code=connection_type.code, name=connection_type.name
    )


async def connection_type_list(
    session: AsyncSession, params: PageParams, q: str | None
) -> ConnectionTypeDetailPage:
    query = (
        select(ConnectionType)
        .where(*matching(q, ConnectionType.name, ConnectionType.code))
        .order_by(ConnectionType.name, ConnectionType.id)
    )
    rows, total = await page_of(session, query, params)
    return ConnectionTypeDetailPage(
        items=[connection_type_detail(row.ConnectionType) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_connection_type(
    session: AsyncSession, body: ConnectionTypeCreate
) -> ConnectionTypeDetail:
    if await is_taken(session, ConnectionType.code, body.code, None):
        raise connection_type_code_taken()
    connection_type = ConnectionType(code=body.code, name=body.name)
    session.add(connection_type)
    await session.commit()
    return connection_type_detail(connection_type)


async def update_connection_type(
    session: AsyncSession, connection_type_id: int, body: ConnectionTypeUpdate
) -> tuple[ConnectionTypeDetail, Changes]:
    connection_type = await session.get(ConnectionType, connection_type_id)
    if connection_type is None:
        raise ApiError(404, "not_found", "Тип подключения не найден")
    if body.code is not None and await is_taken(
        session, ConnectionType.code, body.code, connection_type_id
    ):
        raise connection_type_code_taken()
    changes = apply_changes(connection_type, body.model_dump(exclude_unset=True))
    await session.commit()
    return connection_type_detail(connection_type), changes


# --- Schools -------------------------------------------------------------------------------


def school_code_taken() -> ApiError:
    return ApiError(409, "school_code_taken", "School ID уже занят другой школой")


def point_geom(location: GeoPoint | None) -> ColumnElement[Any] | None:
    """PostGIS point of a map location in WGS 84, SRID 4326."""
    if location is None:
        return None
    return func.ST_SetSRID(func.ST_MakePoint(location.lon, location.lat), 4326)


async def ensure_region(session: AsyncSession, region_id: int) -> None:
    if await session.scalar(select(Region.id).where(Region.id == region_id)) is None:
        raise invalid_field("region_id", "Район или город не найден")


async def create_school(session: AsyncSession, body: SchoolCreate) -> int:
    """Id of the new school; it starts active, with the admin default working hours."""
    await ensure_region(session, body.region_id)
    if await is_taken(session, School.school_code, body.school_code, None):
        raise school_code_taken()
    # The default is copied, so a later change of it does not move this school (ADR-014).
    settings = await session.get(SystemSettings, 1)
    school = School(
        school_code=body.school_code,
        full_name=body.full_name,
        region_id=body.region_id,
        address=body.address,
        geom=point_geom(body.location),
        working_hours=settings.default_working_hours if settings else None,
    )
    session.add(school)
    await session.commit()
    return school.id


async def school_location(session: AsyncSession, school_id: int) -> dict[str, float] | None:
    row = (
        await session.execute(
            select(func.ST_Y(School.geom), func.ST_X(School.geom)).where(School.id == school_id)
        )
    ).one()
    lat, lon = row
    return None if lat is None else {"lat": lat, "lon": lon}


async def update_school(session: AsyncSession, school_id: int, body: SchoolUpdate) -> Changes:
    """Changed fields of the school; ``is_active = false`` deactivates it, history stays."""
    school = await session.get(School, school_id)
    if school is None:
        raise school_not_found()
    if body.region_id is not None:
        await ensure_region(session, body.region_id)
    if body.school_code is not None and await is_taken(
        session, School.school_code, body.school_code, school_id
    ):
        raise school_code_taken()
    updates = body.model_dump(mode="json", exclude_unset=True, exclude={"location"})
    changes = apply_changes(school, updates)
    if "location" in body.model_fields_set:
        old = await school_location(session, school_id)
        new = body.location.model_dump() if body.location else None
        if old != new:
            changes["location"] = {"old": old, "new": new}
            school.geom = point_geom(body.location)
    await session.commit()
    return changes
