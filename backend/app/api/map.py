"""Map API (plan.md §10 «Сводка и карта»): schools on the VKO map as GeoJSON (ТЗ п. 13).

Not a list endpoint: the map needs every school that matches the filters at once for markers
and clusters, so there is no pagination. Popover data (T-23) is carried in feature properties;
the school card is opened by the feature ``id``. The district boundaries and the values of the
filters come from the same router, so every role that sees the map can draw and filter it.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.schemas.map import MapFilterOptions, RegionMapFeatureCollection, SchoolMapFeatureCollection
from app.schemas.statuses import SchoolStatus
from app.services.overview import OverviewFilters, filter_options, region_boundaries, school_map

router = APIRouter(prefix="/map", tags=["map"], dependencies=[Depends(require("map:read"))])


@router.get(
    "/schools",
    summary="Школы на карте ВКО: GeoJSON с фильтрами",
    description=(
        "GeoJSON FeatureCollection (RFC 7946) активных школ в области видимости, без пагинации. "
        "Фильтры provider_id и connection_type_id отбирают школы, у которых есть такая линия. "
        "Статус — на момент period_to (ADR-004), как в сводке; показатели — последний замер "
        "основной линии в периоде, без Wi-Fi (ADR-012). Школа без координат приходит с "
        "geometry = null."
    ),
)
async def get_school_map(
    session: Annotated[AsyncSession, Depends(get_session)],
    region_id: int | None = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    status: Annotated[
        list[SchoolStatus] | None,
        Query(description="Статусы школы; несколько — повтором параметра"),
    ] = None,
    period_from: Annotated[
        AwareDatetime | None,
        Query(description="Начало периода, включительно; по умолчанию — без нижней границы"),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец периода, не включая; по умолчанию — текущий момент"),
    ] = None,
) -> SchoolMapFeatureCollection:
    return await school_map(
        session,
        OverviewFilters(region_id, provider_id, connection_type_id, status),
        period_from=period_from,
        period_to=period_to or datetime.now(UTC),
    )


@router.get(
    "/regions",
    summary="Границы районов и городов ВКО: GeoJSON",
    description=(
        "GeoJSON FeatureCollection всех районов и городов ВКО, по названию; id — значение "
        "фильтра region_id. Граница — справочник, не ограничивается областью видимости."
    ),
)
async def get_region_boundaries(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegionMapFeatureCollection:
    return await region_boundaries(session)


@router.get(
    "/filters",
    summary="Значения фильтров карты и сводки",
    description=(
        "Районы видимых школ, провайдеры и типы подключения видимых линий, по названию: "
        "роль видит только то, что входит в её область видимости."
    ),
)
async def get_filter_options(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MapFilterOptions:
    return await filter_options(session)
