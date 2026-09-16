"""Map API (plan.md §10 «Сводка и карта»): schools on the VKO map as GeoJSON (ТЗ п. 13).

Contract stub: answers 501 until T-22. Not a list endpoint: the map needs every school that
matches the filters at once for markers and clusters, so there is no pagination. Popover data
(T-23) is carried in feature properties; the school card is opened by the feature ``id``.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Security
from pydantic import AwareDatetime

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.map import SchoolMapFeatureCollection
from app.schemas.statuses import SchoolStatus

router = APIRouter(prefix="/map", tags=["map"], dependencies=[Security(user_token)])


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
    raise not_implemented("T-22")
