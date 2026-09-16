"""Panel analytics (plan.md §10, ТЗ п. 5, п. 13): school, district, provider and oblast levels.

Contract stub: answers 501 until T-27. One report per request: rows of the level ordered by
name, the time series and the hour × weekday heatmap of the selection; ranking and sorting
happen in the panel. The school card reads it with ``level=school`` and ``school_id`` (T-28).
Rows stay within the user's scope (ADR-008).
"""

from typing import Annotated

from fastapi import APIRouter, Query, Security
from pydantic import AwareDatetime

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.analytics import AnalyticsLevel, AnalyticsPeriod, AnalyticsReport
from app.schemas.statuses import LineStatus

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Security(user_token)])


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
) -> AnalyticsReport:
    raise not_implemented("T-27")
