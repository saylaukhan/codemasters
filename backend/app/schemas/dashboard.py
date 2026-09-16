"""Overview of the main screen: the eight KPIs of ТЗ п. 4 (plan.md §11, T-22)."""

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """KPIs in the order of ТЗ п. 4 for the applied period.

    Measurement values cover main lines only, without Wi-Fi (ADR-012).
    """

    period_from: datetime
    period_to: datetime
    schools_count: int = Field(ge=0, description="Подключённые школы: активные школы по фильтрам")
    devices_count: int = Field(
        ge=0, description="Зарегистрированные компьютеры, кроме заблокированных"
    )
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
