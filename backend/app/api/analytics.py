"""Panel analytics (plan.md §10, ТЗ п. 5, п. 13): school, district, provider and oblast levels.

One report per request: rows of the level ordered by name, the time series and the hour ×
weekday heatmap of the selection; ranking and sorting happen in the panel. The school card
reads it with ``level=school`` and ``school_id`` (T-25, T-28). ``/analytics/incidents`` is the
same selection counted over ``incidents`` instead of measurements (T-45, ТЗ п. 19). Rows stay
within the user's scope (ADR-008); the numbers are in ``app/services/analytics.py`` and
``app/services/incident_analytics.py``.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.schemas.analytics import (
    AnalyticsLevel,
    AnalyticsPeriod,
    AnalyticsReport,
    IncidentAnalyticsReport,
)
from app.schemas.statuses import LineStatus
from app.services.analytics import AnalyticsFilters, analytics_report
from app.services.incident_analytics import incident_analytics_report

router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(require("analytics:read"))]
)


@router.get(
    "",
    summary="Сводная аналитика: показатели за период, графики, часы ухудшения",
    description=(
        "`rows` — все сущности уровня `level` по name, без пагинации; рейтинг и сортировка — в "
        "панели. `series` и `heatmap` — по всей выборке фильтров: графики одной школы — запрос "
        "с `school_id`. Источники: показатели и счётчики замеров — `m_hourly` / `m_daily` "
        "(T-19), Wi‑Fi не учитывается (ADR-003); `availability_pct` — простои и heartbeat в "
        "рабочие часы (T-16, ADR-014); устойчивое несоответствие — пересчёт T-29. Часы и "
        "сутки — по Asia/Almaty."
    ),
)
async def get_analytics(
    level: Annotated[
        AnalyticsLevel,
        Query(description="Группировка строк: школа, район/город (regions), поставщик или вся ВКО"),
    ],
    period: Annotated[
        AnalyticsPeriod,
        Query(description="today, 7 или 30 суток с текущими, custom — period_from и period_to"),
    ],
    period_from: Annotated[
        AwareDatetime | None,
        Query(description="Начало, включительно; только и обязательно при period=custom"),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец, не включительно; только и обязательно при period=custom"),
    ] = None,
    school_id: int | None = None,
    region_id: Annotated[int | None, Query(description="Район или город (regions)")] = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    line_status: Annotated[
        LineStatus,
        Query(description="Статус учитываемых линий; основные и резервные не смешиваются (п. 10)"),
    ] = "main",
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalyticsReport:
    return await analytics_report(
        session,
        level,
        AnalyticsFilters(school_id, region_id, provider_id, connection_type_id, line_status),
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=datetime.now(UTC),
    )


@router.get(
    "/incidents",
    summary="Инциденты за период: количество, длительность, повторяемость",
    description=(
        "Вкладка «Инциденты» аналитики (ТЗ п. 19, plan.md §7). Инцидент попадает в период по "
        "started_at; длительность — restored_at − started_at, как в карточке (T-41), поэтому "
        "открытый инцидент считается, но длительность не увеличивает. Повторяемость — "
        "инцидентов на линию, приведённых к 30 суткам. Фильтры и область видимости — те же, что "
        "у сводной аналитики: строки стоят на линиях выборки (ADR-008)."
    ),
)
async def get_incident_analytics(
    level: Annotated[
        AnalyticsLevel,
        Query(description="Группировка строк: школа, район/город (regions), поставщик или вся ВКО"),
    ],
    period: Annotated[
        AnalyticsPeriod,
        Query(description="today, 7 или 30 суток с текущими, custom — period_from и period_to"),
    ],
    period_from: Annotated[
        AwareDatetime | None,
        Query(description="Начало, включительно; только и обязательно при period=custom"),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец, не включительно; только и обязательно при period=custom"),
    ] = None,
    school_id: int | None = None,
    region_id: Annotated[int | None, Query(description="Район или город (regions)")] = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    line_status: Annotated[
        LineStatus,
        Query(description="Статус учитываемых линий; основные и резервные не смешиваются (п. 10)"),
    ] = "main",
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentAnalyticsReport:
    return await incident_analytics_report(
        session,
        level,
        AnalyticsFilters(school_id, region_id, provider_id, connection_type_id, line_status),
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=datetime.now(UTC),
    )
