"""Overview API (plan.md §10 «Сводка и карта»): KPIs of the main screen (ТЗ п. 4).

Filters match ``GET /api/map/schools``, so one filter panel of T-22 drives both. Period defaults
differ on purpose: KPIs cover the last 24 h (plan.md §11), the map shows the latest known values.
The counting lives in ``app/services/overview.py``.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.schemas.dashboard import DashboardSummary
from app.schemas.statuses import SchoolStatus
from app.services.overview import OverviewFilters, dashboard_summary

# Period of the KPIs when the request names none (plan.md §11).
DEFAULT_PERIOD = timedelta(hours=24)

router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require("dashboard:read"))]
)


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
        Query(description="Начало периода, включительно; по умолчанию — period_to минус 24 ч"),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец периода, не включая; по умолчанию — текущий момент"),
    ] = None,
) -> DashboardSummary:
    period_to = period_to or datetime.now(UTC)
    return await dashboard_summary(
        session,
        OverviewFilters(region_id, provider_id, connection_type_id, status),
        period_from=period_from or period_to - DEFAULT_PERIOD,
        period_to=period_to,
    )
