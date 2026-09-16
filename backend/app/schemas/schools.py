"""Requests and responses of the panel school API (plan.md §10 «Школы», ТЗ п. 4, п. 13–15).

``school_code`` is the School ID from the customer (ТЗ п. 12, ADR-003). A school is deactivated
with ``is_active``, never deleted (ТЗ п. 20). Contacts are the only personal data about school
staff (ТЗ п. 15, ADR-003). In a PATCH body an absent field stays unchanged, ``null`` clears
a nullable field, and ``null`` for any other field is a 422.
"""

from datetime import date, datetime, time
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    IPvAnyNetwork,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from app.schemas.devices import LatestMeasurement
from app.schemas.pagination import Page
from app.schemas.statuses import LineStatus, QualityStatus, SchoolStatus, Weekday
from app.schemas.thresholds import ThresholdValues

# Sort key of the school list; "-" sorts descending.
type SchoolSort = Literal[
    "full_name",
    "-full_name",
    "school_code",
    "-school_code",
    "region_name",
    "-region_name",
    "devices_count",
    "-devices_count",
    "avg_download_mbps",
    "-avg_download_mbps",
    "avg_upload_mbps",
    "-avg_upload_mbps",
    "avg_ping_ms",
    "-avg_ping_ms",
    "last_measured_at",
    "-last_measured_at",
    "status",
    "-status",
]


class GeoPoint(BaseModel):
    """Map point in WGS 84 (ТЗ п. 13)."""

    lat: float = Field(ge=-90, le=90, examples=[49.9483])
    lon: float = Field(ge=-180, le=180, examples=[82.6286])


class WorkingHours(BaseModel):
    """Working hours of a school: downtime and «no connection» count only inside them.

    ``start`` and ``end`` are local times of day in Asia/Almaty, without an offset (ADR-014).
    Defaults (08:00–18:00, Mon–Sat) are set in the admin panel, not in code (T-37).
    """

    weekdays: list[Weekday] = Field(
        min_length=1, max_length=7, examples=[["mon", "tue", "wed", "thu", "fri", "sat"]]
    )
    start: time = Field(examples=["08:00:00"], description="Местное время Asia/Almaty, без пояса")
    end: time = Field(examples=["18:00:00"], description="Местное время Asia/Almaty, без пояса")

    @model_validator(mode="after")
    def check_hours(self) -> Self:
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("start и end указываются без пояса")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("дни недели не должны повторяться")
        if self.end <= self.start:
            raise ValueError("end должен быть позже start")
        return self


class SchoolListItem(BaseModel):
    """Row of the school list (ТЗ п. 4); averages come from the main line without Wi-Fi."""

    id: int
    school_code: str = Field(description="School ID")
    full_name: str
    region_id: int
    region_name: str
    is_active: bool
    devices_count: int = Field(ge=0, description="Число подключённых ПК (не заблокированных)")
    avg_download_mbps: float | None
    avg_upload_mbps: float | None
    avg_ping_ms: float | None
    thresholds: ThresholdValues | None = Field(
        description="Действующие пороги основной линии для подсветки средних; пусто — линии нет"
    )
    last_measured_at: datetime | None
    status: SchoolStatus


class SchoolListItemPage(Page[SchoolListItem]):
    """Page of the school list."""


class SchoolCreate(BaseModel):
    """New school (ТЗ п. 14, п. 20); working hours start from the admin defaults (ADR-014)."""

    school_code: str = Field(
        min_length=1,
        max_length=64,
        examples=["VKO-UKG-017"],
        description="School ID от заказчика; если его нет — VKO-<код района>-<номер>",
    )
    full_name: str = Field(min_length=1, max_length=500)
    region_id: int
    address: str | None = Field(default=None, max_length=500)
    location: GeoPoint | None = None


class SchoolUpdate(BaseModel):
    """Changes of a school; ``is_active = false`` deactivates it and keeps its history."""

    school_code: Annotated[str, Field(min_length=1, max_length=64)] | SkipJsonSchema[None] = None
    full_name: Annotated[str, Field(min_length=1, max_length=500)] | SkipJsonSchema[None] = None
    region_id: int | SkipJsonSchema[None] = None
    address: str | None = Field(default=None, max_length=500)
    location: GeoPoint | None = None
    is_active: bool | SkipJsonSchema[None] = None
    working_hours: WorkingHours | SkipJsonSchema[None] = None

    @field_validator(
        "school_code", "full_name", "region_id", "is_active", "working_hours", mode="before"
    )
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class SchoolDetail(BaseModel):
    """School card (ТЗ п. 13, DESIGN.md §3.15): identity, place, working hours, current state."""

    id: int
    school_code: str = Field(description="School ID")
    full_name: str
    region_id: int
    region_name: str
    address: str | None
    location: GeoPoint | None
    is_active: bool
    working_hours: WorkingHours
    status: SchoolStatus = Field(description="По последним замерам основной линии и heartbeat")
    on_reserve_line: bool = Field(
        description="Замеры идут через резервную линию: основная недоступна (plan.md §4.5)"
    )
    latest_measurement: LatestMeasurement | None = Field(
        description="Текущие показатели: последний замер основной линии без Wi‑Fi"
    )


class ContractCompliance(BaseModel):
    """Sustained mismatch of a line with its contract speed (ТЗ п. 14, T-29).

    The window and the share threshold come from the settings, not from code.
    """

    sustained_mismatch: bool = Field(description="Доля замеров ниже договора выше порога")
    below_contract_pct: float = Field(
        ge=0, le=100, examples=[62], description="Доля замеров ниже договора за окно, %"
    )
    window_days: int = Field(ge=1, examples=[7])


class LineCreate(BaseModel):
    """New internet line of a school with its contract values (ТЗ п. 10, п. 14)."""

    provider_id: int
    connection_type_id: int | None = None
    line_identifier: str | None = Field(
        default=None, max_length=255, description="Идентификатор линии у поставщика"
    )
    status: LineStatus
    contract_down_mbps: float | None = Field(default=None, gt=0, examples=[50])
    contract_up_mbps: float | None = Field(default=None, gt=0, examples=[50])
    contract_number: str | None = Field(default=None, max_length=255)
    contract_date: date | None = None
    started_at: AwareDatetime | None = Field(default=None, description="Начало эксплуатации")
    ip_ranges: list[IPvAnyNetwork] = Field(
        default_factory=list,
        examples=[["203.0.113.0/24"]],
        description="Внешние IP-диапазоны линии (CIDR) для привязки замеров",
    )


class LineUpdate(BaseModel):
    """Changes of a line; ``status = disabled`` switches it off and keeps its measurements."""

    provider_id: int | SkipJsonSchema[None] = None
    connection_type_id: int | None = None
    line_identifier: str | None = Field(default=None, max_length=255)
    status: LineStatus | SkipJsonSchema[None] = None
    contract_down_mbps: float | None = Field(default=None, gt=0)
    contract_up_mbps: float | None = Field(default=None, gt=0)
    contract_number: str | None = Field(default=None, max_length=255)
    contract_date: date | None = None
    started_at: AwareDatetime | None = None
    ip_ranges: list[IPvAnyNetwork] | SkipJsonSchema[None] = None

    @field_validator("provider_id", "status", "ip_ranges", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class LineDetail(BaseModel):
    """Line of a school: provider, contract and current quality (ТЗ п. 10, п. 14)."""

    id: int
    school_id: int
    provider_id: int
    provider_name: str
    connection_type_id: int | None
    connection_type_name: str | None
    line_identifier: str | None = Field(description="Идентификатор линии у поставщика")
    status: LineStatus
    contract_down_mbps: float | None
    contract_up_mbps: float | None
    contract_number: str | None
    contract_date: date | None
    started_at: datetime | None = Field(description="Начало эксплуатации")
    ip_ranges: list[IPvAnyNetwork] = Field(description="Внешние IP-диапазоны линии (CIDR)")
    quality_status: QualityStatus | None = Field(
        description="Качество линии по её Ethernet-устройствам; пусто — замеров нет"
    )
    contract_compliance: ContractCompliance | None = Field(
        description="Пусто, если договорных скоростей нет"
    )


class LineDetailPage(Page[LineDetail]):
    """Page of the lines of a school."""


class SchoolContactCreate(BaseModel):
    """Person responsible for the internet connection of a school (ТЗ п. 15)."""

    full_name: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32, examples=["+7 700 000 00 00"])
    email: str | None = Field(default=None, max_length=254, examples=["school@example.kz"])
    provider_support_contact: str | None = Field(
        default=None, max_length=500, description="Контакт техподдержки поставщика"
    )


class SchoolContactUpdate(BaseModel):
    """Changes of a contact; ``updated_at`` is set by the server."""

    full_name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    position: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    provider_support_contact: str | None = Field(default=None, max_length=500)

    @field_validator("full_name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value


class SchoolContactDetail(BaseModel):
    """Contact card of a school (ТЗ п. 15)."""

    id: int
    school_id: int
    full_name: str
    position: str | None
    phone: str | None = Field(description="Пусто, если не указан или скрыт по правам роли")
    email: str | None
    provider_support_contact: str | None = Field(description="Контакт техподдержки поставщика")
    updated_at: datetime = Field(description="Дата последнего обновления")


class SchoolContactDetailPage(Page[SchoolContactDetail]):
    """Page of the contacts of a school."""
