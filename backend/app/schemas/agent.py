"""Requests and responses of the agent API (plan.md §10).

Agent requests carry neither ``school_id`` / ``school_code`` nor a line or a quality status:
the school and the line come from the device binding (ADR-005), the status is evaluated on
the server (ADR-004). Time is RFC 3339 with an offset (ADR-014).

Metrics are bounded (T-51): a value outside the range below is not a bad line but a broken
agent, and a record that carries one is refused with ``errors[]`` naming the field (ADR-009)
instead of dragging the averages of a school (ТЗ п. 12).
"""

from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    IPvAnyAddress,
    model_validator,
)

from app.schemas.statuses import ConnectionStatus, IfaceType
from app.schemas.thresholds import ThresholdValues

MAX_BATCH_SIZE = 100

# Upper bounds of the metrics (T-51): ten times the fastest school line of the region, a minute
# of latency and an hour of measuring are all far above anything real and far below the numbers
# a broken agent reports.
MAX_SPEED_MBPS = 10_000.0
MAX_LATENCY_MS = 60_000.0
MAX_DURATION_S = 3600.0

# The queue of the agent holds 30 days (ADR-006); a day on top of that keeps a record right at
# the border. Ahead of the server the clock of a school computer may be minutes off, not hours.
MAX_QUEUE_AGE = timedelta(days=31)
MAX_CLOCK_SKEW = timedelta(minutes=10)


def recent_moment(value: datetime) -> datetime:
    """Moment an agent may report: not from the future and not older than its queue (ADR-006).

    A computer whose clock is wrong would otherwise write history: a measurement dated forward
    hides behind «ещё не наступило», one dated years back changes a period already reported.
    """
    now = datetime.now(UTC)
    if value > now + MAX_CLOCK_SKEW:
        raise ValueError("Момент в будущем: проверьте часы компьютера")
    if value < now - MAX_QUEUE_AGE:
        raise ValueError(f"Момент старше срока очереди агента: {MAX_QUEUE_AGE.days} сут.")
    return value


# Time reported by an agent: RFC 3339 with an offset (ADR-014), inside the window of its queue.
AgentMoment = Annotated[AwareDatetime, AfterValidator(recent_moment)]


class DeviceRegisterRequest(BaseModel):
    """First start of an agent: one-time installation code issued for a school."""

    enrollment_code: str = Field(min_length=1, max_length=64, examples=["VKO-0011-7F3K9-2QD4X"])
    device_uid: str = Field(
        min_length=1, max_length=128, description="Постоянный идентификатор ПК от агента"
    )
    hostname: str | None = Field(default=None, max_length=255)
    os: str | None = Field(default=None, max_length=255)
    agent_version: str = Field(max_length=32, examples=["0.1.0"])
    room: str | None = Field(
        default=None, max_length=255, description="Кабинет из параметра установки ROOM"
    )


class DeviceRegisterResponse(BaseModel):
    """Credentials of a registered device; the token is shown once (argon2 hash on server)."""

    device_id: int
    device_token: str


class HeartbeatRequest(BaseModel):
    """Liveness signal of the agent, every 5 minutes by default (plan.md §4.2)."""

    sent_at: AwareDatetime
    agent_version: str = Field(max_length=32)


class ScheduleSlot(BaseModel):
    """Measurement window; the agent picks a random moment inside it (plan.md §4.2)."""

    start: time = Field(examples=["08:30:00"])
    end: time = Field(examples=["09:00:00"])


class SpeedtestServers(BaseModel):
    """Measurement servers: LibreSpeed is the main one, ndt7 the fallback (ADR-012)."""

    librespeed_url: str = Field(examples=["https://speedtest.example.kz"])
    ndt7_url: str | None = None


class AgentConfigResponse(BaseModel):
    """Agent configuration; nothing of it is hard-coded in the agent (ТЗ п. 11, п. 20)."""

    timezone: str = Field(examples=["Asia/Almaty"], description="Пояс слотов расписания")
    schedule_slots: list[ScheduleSlot] = Field(min_length=3, max_length=5)
    heartbeat_interval_s: int = Field(ge=1, examples=[300])
    config_refresh_interval_s: int = Field(ge=1, examples=[900])
    speedtest: SpeedtestServers
    thresholds: ThresholdValues
    latest_version: str | None = Field(default=None, examples=["0.2.0"])
    token_rotation_required: bool = Field(
        default=False,
        description="Администратор запросил новый токен: агент вызывает POST /api/agent/token "
        "текущим токеном и сохраняет выданный (T-36)",
    )


class WhoAmIResponse(BaseModel):
    """External IP of the request as seen by the server."""

    external_ip: IPvAnyAddress


class MeasurementCreate(BaseModel):
    """One measurement: raw values only; fields of ``measurements`` from plan.md §5."""

    measurement_uuid: UUID = Field(description="Генерирует агент; ключ идемпотентности")
    measured_at: AgentMoment = Field(description="Момент замера на ПК")
    connection_status: ConnectionStatus
    download_mbps: float | None = Field(default=None, ge=0, le=MAX_SPEED_MBPS)
    upload_mbps: float | None = Field(default=None, ge=0, le=MAX_SPEED_MBPS)
    ping_ms: float | None = Field(default=None, ge=0, le=MAX_LATENCY_MS)
    jitter_ms: float | None = Field(default=None, ge=0, le=MAX_LATENCY_MS)
    packet_loss_pct: float | None = Field(default=None, ge=0, le=100)
    duration_s: float | None = Field(default=None, ge=0, le=MAX_DURATION_S)
    external_ip: IPvAnyAddress | None = None
    server: str | None = Field(default=None, description="Сервер и метод замера")
    iface_type: IfaceType | None = None
    agent_version: str = Field(max_length=32)


class MeasurementAccepted(BaseModel):
    """Measurement stored (201); the agent deletes it from the queue."""

    measurement_uuid: UUID
    received_at: datetime


class MeasurementBatchRequest(BaseModel):
    """Queue resend: up to 100 measurements per request (ADR-006).

    An invalid item rejects the whole request with 422; ``errors[].field`` starts with
    ``items[<index>]`` and names the field out of range (``items[3].ping_ms``, T-51), so the
    agent knows which records the server will never accept.
    """

    items: list[MeasurementCreate] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class MeasurementBatchResult(BaseModel):
    """Result for one item, in request order: 201 — stored, 409 — already stored.

    Both mean "delete from the queue" (ADR-006); ``type`` is the problem code for 409.
    """

    measurement_uuid: UUID
    status: Literal[201, 409]
    type: str | None = Field(default=None, examples=["duplicate_measurement"])


class MeasurementBatchResponse(BaseModel):
    results: list[MeasurementBatchResult]


class OutageCreate(BaseModel):
    """Period without connection recorded by the agent (T-12).

    Idempotency key is the device (from the token) plus ``started_at``: a resent outage gets
    409 ``duplicate_outage``, which, like 201, means "delete from the queue" (ADR-006).
    """

    started_at: AgentMoment
    ended_at: AgentMoment

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at раньше started_at")
        return self


class OutageAccepted(BaseModel):
    id: int


class AgentReleaseResponse(BaseModel):
    """Latest agent release for self-update (plan.md §4.6)."""

    version: str = Field(examples=["0.2.0"])
    channel: Literal["pilot", "stable"]
    download_url: str
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    released_at: datetime
