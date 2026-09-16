"""Overview API (plan.md §10 «Сводка и карта»): KPIs of the main screen (ТЗ п. 4).

Contract stub: answers 501 until T-22. Filters match ``GET /api/map/schools``, so one filter
panel of T-22 drives both. Period defaults differ on purpose: KPIs cover the last 24 h
(plan.md §11), the map shows the latest known values.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Security
from pydantic import AwareDatetime

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.dashboard import DashboardSummary
from app.schemas.statuses import SchoolStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Security(user_token)])


@router.get(
    "/summary",
    summary="Сводка главного экрана: KPI",
    description=(
        "Восемь KPI из ТЗ п. 4 по школам в области видимости, отобранным фильтрами; status — "
        "статус школы на момент period_to (ADR-004), как на карте. Фильтры provider_id и "
        "connection_type_id отбирают школы, у которых есть такая линия. Замеры, средние и "
        "проблемные устройства — за период, по основным линиям, без Wi-Fi (ADR-012)."
    ),
)
async def get_dashboard_summary(
    region_id: int | None = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    status: Annotated[
        list[SchoolStatus] | None,
        Query(description="Статусы школы; несколько — повтором параметра"),
    ] = None,
    period_from: Annotated[
        AwareDatetime | None,
        Query(description="Начало периода, включительно; по умолчанию — period_to минус 24 ч"),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец периода, не включая; по умолчанию — текущий момент"),
    ] = None,
) -> DashboardSummary:
    raise not_implemented("T-22")
