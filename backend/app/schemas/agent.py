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

# Ahead of the server the clock of a school computer may be minutes off, not hours. This is
# about clocks, not about policy, so it stays a constant of the contract.
MAX_CLOCK_SKEW = timedelta(minutes=10)

# How far back a moment may point is ``settings.agent_queue_retention_days`` — the same value
# the agent keeps its queue by (ТЗ п. 11, п. 20; ADR-004, ADR-006). A day on top of it keeps a
# record that sat at the very border of the queue: the agent still had the right to send it,
# and while a long resend is running the border moves on.
QUEUE_WINDOW_MARGIN = timedelta(days=1)


# How long a measurement asked for in the panel waits for its agent (T-79). The agent hears
# about it in the answer of its heartbeat, so a computer that is on takes the request within one
# heartbeat interval; a computer that is off must not measure at night, when the administrator
# who pressed the button has long left the page. This is about the waiting of a person, not
# about policy, so it stays a constant of the contract like ``MAX_CLOCK_SKEW``.
MEASURE_REQUEST_TTL = timedelta(hours=1)


def live_measure_request(requested_at: datetime | None, now: datetime) -> datetime | None:
    """Moment of a measurement request while it still waits; ``None`` for none and for a stale one.

    The agent and the panel judge a request by the same rule: an agent is never handed one it
    should no longer perform, and the card of a device never marks one as pending.
    """
    if requested_at is None or now - requested_at > MEASURE_REQUEST_TTL:
        return None
    return requested_at


def queue_window(retention_days: int) -> timedelta:
    """How old a moment of an agent may be with a queue kept ``retention_days`` days."""
    return timedelta(days=retention_days) + QUEUE_WINDOW_MARGIN


def too_old_message(window: timedelta) -> str:
    """Message of a moment older than the window; the agent will never get it accepted."""
    return f"Момент старше срока очереди агента: {window.days} сут."


def not_in_the_future(value: datetime) -> datetime:
    """Moment an agent may report (ADR-006): the half of the check that needs no database.

    A computer whose clock runs forward would otherwise write history no one sees: a
    measurement dated ahead hides behind «ещё не наступило». The other half — a moment older
    than the queue of the agent — is a setting now, so it is checked where there is a session
    to read it, in ``app/api/agent.py``; the answer stays the same 422 naming the field
    (ADR-009).
    """
    if value > datetime.now(UTC) + MAX_CLOCK_SKEW:
        raise ValueError("Момент в будущем: проверьте часы компьютера")
    return value


# Time reported by an agent: RFC 3339 with an offset (ADR-014) and not from the future. Whether
# it also fits the window of the queue is checked in ``app/api/agent.py`` (``check_queue_window``):
# the width of that window is ``agent_queue_retention_days`` of the settings, and reading it needs
# a session, which a validator of a schema has not got.
AgentMoment = Annotated[AwareDatetime, AfterValidator(not_in_the_future)]


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
    """Credentials of a registered device; the token is shown once (only its hash is kept)."""

    device_id: int
    device_token: str


class HeartbeatRequest(BaseModel):
    """Liveness signal of the agent, every 5 minutes by default (plan.md §4.2)."""

    sent_at: AwareDatetime
    agent_version: str = Field(max_length=32)


class HeartbeatResponse(BaseModel):
    """Answer of a heartbeat: what the server asks of the agent besides its schedule (T-79)."""

    measure_requested_at: datetime | None = Field(
        default=None,
        description="Администратор запросил замер: агент делает один внеплановый замер и "
        "запоминает этот момент, чтобы не повторить запрос после перезапуска службы. Пусто — "
        "запроса нет или он старше часа",
    )


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
    queue_retention_days: int = Field(
        ge=1,
        le=365,
        examples=[30],
        description="Сколько суток агент хранит замер в очереди; старше — сервер не примет "
        "(ADR-006)",
    )
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
