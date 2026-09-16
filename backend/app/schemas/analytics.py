"""Response of the panel analytics (ТЗ п. 5, п. 13; plan.md §10, §11).

Sources, never raw measurements: metric stats, counts and percentages of measurements — the
continuous aggregates ``m_hourly`` / ``m_daily`` (T-19); ``availability_pct`` — outages and
heartbeats in working hours (T-16, ADR-014); sustained mismatch — the T-29 recompute. Hours and
days are Asia/Almaty (ADR-014), datetimes are UTC RFC 3339. Percentages are 0–100. A "problem"
measurement has the quality status ``unstable``, ``critical`` or ``offline`` (ADR-004).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.statuses import Weekday
from app.schemas.thresholds import ThresholdValues

# Grouping of report rows, names of plan.md §10: school — per school; district — per row of
# ``regions`` (district or city); provider — per provider; region — the whole VKO oblast.
type AnalyticsLevel = Literal["school", "district", "provider", "region"]

# Period preset: today, rolling 7 or 30 days including today, or explicit bounds.
type AnalyticsPeriod = Literal["today", "week", "month", "custom"]

# Bucket of the time series: an hour (m_hourly) or a day (m_daily).
type AnalyticsGranularity = Literal["hour", "day"]


class MetricStats(BaseModel):
    """Average, minimum and maximum of one metric over the period (ТЗ п. 5)."""

    avg: float
    min: float
    max: float


class AnalyticsRow(BaseModel):
    """One entity of the level: aggregates for the period.

    A metric is null when no measurement of the period has a value for it (offline only).
    """

    id: int | None = Field(
        description="id школы, района/города (regions) или поставщика; null при level=region"
    )
    name: str | None = Field(
        description="Наименование школы, района/города или поставщика; null при level=region"
    )
    measurements_count: int = Field(ge=0)
    problem_count: int = Field(ge=0)
    problem_pct: float | None = Field(
        ge=0, le=100, description="Доля проблемных замеров, %; null без замеров"
    )
    download_mbps: MetricStats | None
    upload_mbps: MetricStats | None
    ping_ms: MetricStats | None
    availability_pct: float | None = Field(
        ge=0,
        le=100,
        description="Доступность: 1 − простой / время наблюдения в рабочие часы (T-16, ADR-014)",
    )
    below_contract_pct: float | None = Field(
        ge=0,
        le=100,
        description="Доля замеров ниже договорной скорости, %; null, если договорных значений нет",
    )
    sustained_mismatch_lines_count: int | None = Field(
        ge=0,
        description=(
            "Линий с устойчивым несоответствием договору; null — признак ещё не рассчитан (T-29)"
        ),
    )


class AnalyticsSeriesPoint(BaseModel):
    """One hour or day of the time series, over all rows of the report together."""

    bucket_start: datetime = Field(description="Начало часа или суток по Asia/Almaty")
    measurements_count: int = Field(ge=1)
    problem_count: int = Field(ge=0)
    problem_pct: float = Field(ge=0, le=100)
    avg_download_mbps: float | None
    avg_upload_mbps: float | None
    avg_ping_ms: float | None


class AnalyticsHeatmapCell(BaseModel):
    """Hour of a weekday over all days of the period, over all rows together (T-28)."""

    weekday: Weekday
    hour: int = Field(ge=0, le=23, description="Час суток по Asia/Almaty")
    measurements_count: int = Field(ge=1)
    problem_count: int = Field(ge=0)
    problem_pct: float = Field(ge=0, le=100)


class AnalyticsReport(BaseModel):
    """Analytics of one level for a period: rows, time series and hour × weekday heatmap.

    Rows are grouped by ``level``; the series and the heatmap cover the whole selection of the
    filters, so charts of one school are a request with ``school_id``.
    """

    period_from: datetime = Field(description="Начало периода, включительно")
    period_to: datetime = Field(description="Конец периода, не включительно")
    granularity: AnalyticsGranularity = Field(
        description="Шаг series, выбирает сервер: hour при period=today, иначе day"
    )
    thresholds: ThresholdValues = Field(
        description=(
            "Пороги для отметок на графиках: профиль линии, если в выборке одна линия, районный "
            "при region_id, иначе глобальный (ADR-004). Замеры оценены по своему "
            "thresholds_snapshot, а не по этим значениям"
        )
    )
    availability_min_pct: float = Field(
        ge=0, le=100, description="Порог доступности из settings (п. 11, T-37)"
    )
    rows: list[AnalyticsRow] = Field(
        description=(
            "Все сущности уровня в области видимости и фильтрах, в том числе без замеров за "
            "период, по name; без пагинации, рейтинг и сортировка — в панели"
        )
    )
    series: list[AnalyticsSeriesPoint] = Field(
        description="По возрастанию bucket_start; часы и сутки без замеров не передаются"
    )
    heatmap: list[AnalyticsHeatmapCell] = Field(description="Ячейки без замеров не передаются")
