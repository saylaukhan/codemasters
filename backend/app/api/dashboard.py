"""Overview API (plan.md §10 «Сводка и карта»): the main screen (ТЗ п. 4, T-22, T-60).

Filters match ``GET /api/map/schools``, so one filter panel of T-22 drives both. Period defaults
differ on purpose: KPIs cover the last 24 h (plan.md §11), the map shows the latest known values.
The counting lives in ``app/services/overview.py`` and ``app/services/attention.py``.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.schemas.dashboard import AttentionPage, DashboardSummary
from app.schemas.statuses import SchoolStatus
from app.services.attention import attention_list
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
        "проблемные устройства — за период, по основным линиям, без Wi-Fi (ADR-012). "
        "status_counts считается до фильтра по статусу, поэтому сумма пяти чисел не меняется "
        "при клике по колонке полосы; schools_total_count включает отключённые школы. "
        "previous — те же показатели за предыдущий период такой же длины по тем же школам; "
        "null, если за тот период не было ни замеров, ни heartbeat."
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


@router.get(
    "/attention",
    summary="Требуют внимания: школы, инциденты и обращения, которые ждут человека",
    description=(
        "Школы со статусом «Нет соединения» и «Критично» на момент period_to, инциденты без "
        "ответственного и обращения «Передан поставщику» без движения дольше окон из настроек "
        "(attention_incident_unassigned_hours, attention_appeal_no_answer_hours). Фильтры "
        "отбирают школы так же, как GET /api/dashboard/summary. Порядок: severity по "
        "возрастанию, затем since от старого к новому; total — число строк до ограничения "
        "limit, для подписи «Ещё N школ»."
    ),
)
async def get_attention(
    session: Annotated[AsyncSession, Depends(get_session)],
    region_id: int | None = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Момент, на который собирается список; по умолчанию — текущий"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Сколько строк вернуть")] = 10,
) -> AttentionPage:
    now = period_to or datetime.now(UTC)
    return await attention_list(
        session,
        OverviewFilters(region_id, provider_id, connection_type_id),
        now=now,
        limit=limit,
    )
