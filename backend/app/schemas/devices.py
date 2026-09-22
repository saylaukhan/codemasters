"""Requests and responses of the panel device API (plan.md §10 «Устройства», ТЗ п. 4).

The school and the line of a device come from its monitoring point (ADR-005). Blocking keeps
the device and its measurements (ТЗ п. 16, п. 20). Quality is evaluated on the server and each
measurement keeps the thresholds it was evaluated with (ADR-004). Time is UTC, RFC 3339 (ADR-014).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.agent_releases import AgentChannel
from app.schemas.calendar import CalendarKind
from app.schemas.pagination import Page
from app.schemas.statuses import (
    ConnectionStatus,
    DeviceStatus,
    IfaceType,
    LineStatus,
    QualityStatus,
    SchoolStatus,
)
from app.schemas.thresholds import ThresholdValues


class LatestMeasurement(BaseModel):
    """Values of the latest measurement shown in cards and lists (ТЗ п. 4, п. 13)."""

    measured_at: datetime = Field(description="Момент замера на ПК")
    connection_status: ConnectionStatus
    download_mbps: float | None
    upload_mbps: float | None
    ping_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float | None
    iface_type: IfaceType | None
    thresholds_snapshot: ThresholdValues | None = Field(
        description="Пороги, применённые при оценке этого замера (ТЗ п. 11)"
    )
    quality_status: QualityStatus | None = Field(description="Пусто, если замер не оценён")


class DeviceListItem(BaseModel):
    """Computer of a school in the school card (ТЗ п. 4)."""

    id: int = Field(description="Device ID")
    device_uid: str = Field(description="Постоянный идентификатор ПК от агента")
    hostname: str | None
    monitoring_point_id: int
    monitoring_point_name: str
    room: str | None = Field(description="Кабинет точки мониторинга")
    line_id: int
    line_status: LineStatus
    agent_version: str | None
    last_seen_at: datetime | None = Field(description="Последняя связь с агентом")
    status: DeviceStatus
    update_channel: AgentChannel = Field(
        description="Канал обновления агента: pilot получает релиз раньше остальных"
    )
    current_status: SchoolStatus = Field(
        description="По правилу T-16: heartbeat в рабочие часы и последний замер; "
        "вне рабочих часов — no_data"
    )
    quiet_reason: CalendarKind | None = Field(
        default=None,
        description="Почему нет данных: событие календаря школы на этот момент; null — обычный",
    )
    latest_measurement: LatestMeasurement | None


class DeviceListItemPage(Page[DeviceListItem]):
    """Page of the devices of a school."""


class DeviceDetail(DeviceListItem):
    """Device card (ТЗ п. 4): the list row plus the school, the OS and the registration time."""

    os: str | None
    school_id: int
    school_code: str = Field(description="School ID")
    school_name: str
    registered_at: datetime
    token_rotation_requested_at: datetime | None = Field(
        description="Запрошена замена токена; пусто — агент уже получил новый или замены не было"
    )


class DeviceDetailPage(Page[DeviceDetail]):
    """Page of the devices of the admin list."""


class DeviceUpdate(BaseModel):
    """Changes of a device: its monitoring point (T-36) and its update channel (T-50).

    The school and the line of new measurements follow the point, measurements already taken
    keep theirs (ADR-005); the channel decides which release the agent installs.
    """

    monitoring_point_id: int | SkipJsonSchema[None] = None
    update_channel: AgentChannel | SkipJsonSchema[None] = None

    @field_validator("monitoring_point_id", "update_channel", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class MeasurementListItem(LatestMeasurement):
    """Measurement in the history: raw values, the line and the server evaluation (plan.md §5).

    ``line_id`` is the line the measurement went through, possibly the reserve one (plan.md §4.5).
    """

    measurement_uuid: UUID
    received_at: datetime = Field(
        description="Приём сервером; разница с measured_at — время в офлайн-очереди"
    )
    line_id: int
    duration_s: float | None
    external_ip: IPvAnyAddress | None
    server: str | None = Field(description="Сервер и метод замера")
    agent_version: str | None
    contract_ok: bool | None = Field(
        description="Факт не ниже договорной скорости линии; пусто — договорных значений нет"
    )


class MeasurementListItemPage(Page[MeasurementListItem]):
    """Page of the measurement history of a device, newest first."""


class EnrollmentCodeCreate(BaseModel):
    """Request for a one-time agent installation code for a school (plan.md §4.1)."""

    school_id: int


class EnrollmentCodeIssued(BaseModel):
    """Issued installation code: shown once, the server keeps only its hash (ADR-005)."""

    code: str = Field(
        examples=["VKO-0011-7F3K9-2QD4X"],
        description="Код для параметра установки ENROLL_CODE; повторно не показывается",
    )
    school_id: int
    expires_at: datetime = Field(
        examples=["2026-09-24T04:00:00Z"],
        description="Окончание срока действия: enrollment_code_ttl_days системных настроек, "
        "по умолчанию 7 дней с выдачи (ADR-005)",
    )
