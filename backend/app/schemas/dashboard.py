"""Overview of the main screen: the KPIs of ТЗ п. 4 (plan.md §11, T-22) and the rows that ask
for a person now (docs/design/README.md §4.1, T-60)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.statuses import IncidentMetric, SchoolStatus

# What a row of «Требуют внимания» points at: the school itself, its incident or its appeal.
type AttentionKind = Literal["school", "incident", "appeal"]

# Why the row is there; ``AttentionItem.severity`` follows this order (docs/design/README.md §4.1).
type AttentionReason = Literal["offline", "critical", "incident_unassigned", "appeal_unanswered"]


class SchoolStatusCounts(BaseModel):
    """Schools per status at ``period_to`` (ТЗ п. 13, ADR-004).

    Counted over the schools the district, provider and connection-type filters select, before
    the status filter narrows them: the five numbers always sum to the same selection, so a
    click on a column of the status strip does not rewrite the strip (docs/design/README.md §4.1).
    """

    normal: int = Field(ge=0)
    unstable: int = Field(ge=0)
    critical: int = Field(ge=0)
    offline: int = Field(ge=0)
    no_data: int = Field(ge=0, description="Показ, а не статус качества (ТЗ п. 13, ADR-004)")


class DashboardPeriodKpis(BaseModel):
    """KPIs that depend on the period, so the previous period of equal length also answers them.

    Measurement values cover main lines only, without Wi-Fi (ADR-012).
    """

    active_devices_count: int = Field(
        ge=0, description="Устройства, выходившие на связь за период: heartbeat или замер"
    )
    measurements_count: int = Field(ge=0, description="Замеры за период")
    avg_download_mbps: float | None = Field(description="null — замеров за период нет")
    avg_upload_mbps: float | None = Field(description="null — замеров за период нет")
    avg_ping_ms: float | None = Field(description="null — замеров за период нет")
    problem_devices_count: int = Field(
        ge=0,
        description="Устройства, чей последний замер за период — unstable, critical или offline",
    )


class DashboardSummary(DashboardPeriodKpis):
    """The KPIs of ТЗ п. 4 for the applied period, with the status strip and the previous period.

    The period-dependent half is inherited, so the very same six numbers describe ``previous``:
    the period of equal length that ends at ``period_from``, counted over the same schools. It is
    null while that period holds neither a measurement nor a heartbeat, and the panel says
    «первые данные» instead of a delta (docs/design/README.md §4.1).
    """

    period_from: datetime
    period_to: datetime
    schools_count: int = Field(ge=0, description="Подключённые школы: активные школы по фильтрам")
    schools_total_count: int = Field(
        ge=0,
        description="Школы тех же фильтров вместе с отключёнными: подпись «350 из 366 в реестре»",
    )
    devices_count: int = Field(
        ge=0, description="Зарегистрированные компьютеры, кроме заблокированных"
    )
    status_counts: SchoolStatusCounts = Field(
        description="Школы по статусам на period_to, до применения фильтра по статусу"
    )
    previous: DashboardPeriodKpis | None = Field(
        description="Те же показатели за предыдущий период той же длины; null — данных за него нет"
    )


class AttentionItem(BaseModel):
    """One row of «Требуют внимания»: what is wrong, where, and since when (§4.1)."""

    kind: AttentionKind
    reason: AttentionReason
    severity: int = Field(
        ge=1,
        le=4,
        description="Ключ сортировки, меньше — хуже: 1 «Нет соединения», 2 «Критично», "
        "3 инцидент без ответственного, 4 обращение без ответа",
    )
    school_id: int
    school_code: str
    school_name: str
    region_name: str
    provider_name: str | None = Field(
        description="Поставщик: у школы — основной линии, у инцидента и обращения — их линии"
    )
    status: SchoolStatus | None = Field(
        description="Статус школы; null у строки инцидента и обращения"
    )
    incident_id: int | None
    incident_number: str | None
    appeal_id: int | None
    appeal_number: str | None
    metric: IncidentMetric | None = Field(
        description="Первое основание инцидента: из него строится причина словами (§4.1)"
    )
    since: datetime = Field(
        description="Школа — когда её в последний раз слышали или мерили, иначе period_to; "
        "инцидент — started_at; обращение — sent_at"
    )


class AttentionPage(BaseModel):
    """Rows that ask for a person at ``period_to``, the worst first (§4.1)."""

    period_to: datetime
    total: int = Field(ge=0, description="Сколько строк до ограничения limit: подпись «Ещё N школ»")
    items: list[AttentionItem]
