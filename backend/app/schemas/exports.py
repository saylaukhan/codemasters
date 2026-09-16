"""Requests and responses of exports (ТЗ п. 9; plan.md §10 «Экспорт», §12; T-30…T-33).

One request builds one file: raw measurements, aggregates per school or the PDF report of
a school. Times in files are Asia/Almaty, column headers in XLSX/CSV are Russian, JSON keys
are the column codes (ADR-014, T-30). A "problem" measurement is ``unstable``, ``critical`` or
``offline`` (ADR-004).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas.statuses import QualityStatus

# What is exported: measurements (T-30), one row per school (T-31), PDF report of a school (T-32).
type ExportMode = Literal["raw", "aggregates", "school_report"]

# File format; json is an array of objects keyed by the column codes.
type ExportFormat = Literal["xlsx", "csv", "json", "pdf"]

# State of the file: built in the request until T-33, in the background from T-33.
type ExportStatus = Literal["pending", "ready", "failed"]

# Column of a raw export; ``date`` and ``time`` are the measured_at in Asia/Almaty.
type ExportColumn = Literal[
    "school_name",
    "hostname",
    "room",
    "date",
    "time",
    "download_mbps",
    "upload_mbps",
    "ping_ms",
    "jitter_ms",
    "packet_loss_pct",
    "quality_status",
    "school_code",
    "device_id",
    "line_status",
    "connection_status",
    "iface_type",
    "duration_s",
    "external_ip",
    "server",
    "agent_version",
]

# Minimum columns of ТЗ п. 9 in their order: every raw export contains them (invariant 16).
MIN_EXPORT_COLUMNS: tuple[ExportColumn, ...] = (
    "school_name",
    "hostname",
    "room",
    "date",
    "time",
    "download_mbps",
    "upload_mbps",
    "ping_ms",
    "jitter_ms",
    "packet_loss_pct",
    "quality_status",
)

MODE_FORMATS: dict[ExportMode, tuple[ExportFormat, ...]] = {
    "raw": ("xlsx", "csv", "json"),
    "aggregates": ("xlsx", "csv", "json"),
    "school_report": ("pdf",),
}


class ExportCreate(BaseModel):
    """Export request: mode, format, period, filters and columns (ТЗ п. 9, DESIGN.md §3.24)."""

    mode: ExportMode
    format: ExportFormat = Field(
        description="raw и aggregates — xlsx, csv, json; school_report — pdf"
    )
    period_from: AwareDatetime = Field(description="Начало периода по measured_at, включительно")
    period_to: AwareDatetime = Field(description="Конец периода, не включается")
    school_ids: list[int] = Field(
        default_factory=list,
        description="Пусто — все школы в области видимости; для school_report — ровно одна",
    )
    device_ids: list[int] = Field(
        default_factory=list, description="Только raw: ПК выбранных школ; пусто — все"
    )
    statuses: list[QualityStatus] = Field(
        default_factory=list, description="Только raw: статусы замера; пусто — все"
    )
    columns: list[ExportColumn] = Field(
        default=list(MIN_EXPORT_COLUMNS),
        description="Только raw: колонки в порядке файла; минимальный набор ТЗ п. 9 обязателен",
    )

    @model_validator(mode="after")
    def check_request(self) -> Self:
        if self.period_to <= self.period_from:
            raise ValueError("period_to должен быть позже period_from")
        if self.format not in MODE_FORMATS[self.mode]:
            formats = ", ".join(MODE_FORMATS[self.mode])
            raise ValueError(f"режим {self.mode} выгружается только в {formats}")
        if self.mode != "raw" and (
            self.device_ids or self.statuses or "columns" in self.model_fields_set
        ):
            raise ValueError("device_ids, statuses и columns задаются только для режима raw")
        if self.mode == "school_report" and len(self.school_ids) != 1:
            raise ValueError("school_report строится ровно по одной школе в school_ids")
        missing = [column for column in MIN_EXPORT_COLUMNS if column not in self.columns]
        if missing:
            raise ValueError(f"в columns нет обязательных колонок ТЗ п. 9: {', '.join(missing)}")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("колонки не должны повторяться")
        return self


class ExportJob(BaseModel):
    """Export and the state of its file; the file itself is ``GET /api/exports/{id}``."""

    id: int
    status: ExportStatus
    mode: ExportMode
    format: ExportFormat
    rows_count: int | None = Field(
        ge=0,
        description="Строк в файле: замеров (raw, таблица school_report) или школ (aggregates); "
        "null — файл ещё не сформирован",
    )
    created_at: datetime
    expires_at: datetime | None = Field(
        examples=["2026-09-24T04:00:00Z"],
        description="Когда файл удаляется и выгрузка отвечает 404; срок — из settings "
        "(по умолчанию 7 дней); null — файл ещё не сформирован",
    )
    error: str | None = Field(description="Причина для человека при status=failed")
