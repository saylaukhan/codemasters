"""T-56: load profile of the four heaviest endpoints on simulator data (plan.md §14, этап 6).

The other tests of this package run against the throwaway container of ``conftest.py``, which is
empty: nothing there says how ``GET /api/analytics`` behaves on 350 schools and three months of
measurements. This module measures exactly that, so it needs the opposite — a database already
filled by ``make seed`` and ``make simulate`` (T-55) and kept between runs. Its DSN comes in
``VKO_LOAD_DATABASE_URL``; without it every test here is skipped, and that is what keeps the
load run out of ``make check-backend`` and CI, which call ``pytest`` without ``-m``.

Two measurements, the two the task asks for:

* ``test_endpoint_latency`` — p50 / p95 / max of ``GET /api/map/schools``,
  ``GET /api/dashboard/summary``, ``GET /api/analytics`` and ``POST /api/measurements/batch``,
  one request at a time, with the number of SQL statements one answer costs;
* ``test_concurrent_batches`` — the queues of ``VKO_LOAD_DEVICES`` agents resent at once, which
  must all be accepted (ТЗ п. 3; ADR-006: a resent queue never loses a record).

What the numbers are, and what they are not: the application runs in this process over ASGI on
an engine whose pool repeats the one a deployment gets by default — ``app/core/db.py`` sets
neither ``pool_size`` nor ``max_overflow`` — so RLS of ADR-008 and the rate limit of T-51 apply
as they do behind Caddy. One event loop here and one uvicorn process there
(``backend/Dockerfile``), so the width is the same as well, and what is left is that a run of
this file hashes its own tokens instead of issuing them. The token check itself is no longer
part of the cost — a device token is hashed with sha256 now, not argon2id
(``app/core/security.py``) — but the run still prints it, so whoever reads the table can see
that it is a rounding error and stop subtracting it.

This file has never been executed: it was written in a session with neither Docker nor
``backend/.venv``. The three criteria of «Сделано, когда» of T-56 are met by a run, not by the
scenario — docs/product/load-test.md says how to make one and what to write down.
"""

import asyncio
import math
import os
import statistics
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.db import get_session
from app.core.security import (
    format_device_token,
    hash_secret,
    hash_token,
    new_device_secret,
    verify_secret,
    verify_token,
)
from app.main import create_app
from app.models import (
    Device,
    Heartbeat,
    Measurement,
    MonitoringPoint,
    Outage,
    SystemSettings,
    User,
)
from tests.factories import bearer

DSN_ENV = "VKO_LOAD_DATABASE_URL"
DSN = os.getenv(DSN_ENV, "")

pytestmark = pytest.mark.skipif(
    not DSN,
    reason=(
        f"нагрузочный тест T-56: задайте {DSN_ENV} на базу с данными симулятора, "
        "см. docs/product/load-test.md"
    ),
)


def setting(name: str, default: int) -> int:
    """Whole number from the environment; anything that is not one falls back to ``default``."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


# Calls of one endpoint in the sequential phase: enough for a p95 that is not one outlier,
# short enough for a run of a couple of minutes. Above ~100 the per-device limit of T-51
# (120 per 60 s) starts refusing, and then the phase measures the limiter.
REPEATS = setting("VKO_LOAD_REPEATS", 20)
# Agents sending at once — the thousand computers of ТЗ п. 3.
DEVICES = setting("VKO_LOAD_DEVICES", 1000)
# Records in one batch; the contract allows 100 (``MAX_BATCH_SIZE``), a resent day is about 5.
BATCH_ITEMS = setting("VKO_LOAD_BATCH_ITEMS", 10)
# Connections of the pool. The defaults are the defaults of SQLAlchemy, which is what a
# deployment runs on; raising them turns the run into an experiment about the pool, and the
# values then belong in the journal next to the numbers.
POOL = setting("VKO_LOAD_POOL", 5)
OVERFLOW = setting("VKO_LOAD_OVERFLOW", 10)
# With it the budgets below become assertions; without it they are a verdict in the table.
STRICT = bool(os.getenv("VKO_LOAD_STRICT"))

# Proposed budget of the answer, p95, milliseconds. NOT a requirement of ТЗ — it names none.
# These are the working target of plan.md §14 «нагрузочный тест», and the lead confirms them
# before they are quoted anywhere as a criterion of acceptance.
BUDGET_MS = {
    "GET /api/map/schools": 2000.0,
    "GET /api/dashboard/summary": 1500.0,
    "GET /api/analytics (month, district)": 3000.0,
    "POST /api/measurements/batch": 300.0,
}


@dataclass(frozen=True)
class Call:
    """One endpoint of the profile: the name it gets in the table and how it is called."""

    name: str
    method: str
    url: str
    body: bool = False


@dataclass
class Timing:
    """Durations of one endpoint, milliseconds, and the SQL statements one answer costs."""

    name: str
    durations: list[float]
    statements: int

    @property
    def p50(self) -> float:
        return statistics.median(self.durations)

    @property
    def p95(self) -> float:
        return percentile(self.durations, 0.95)

    @property
    def worst(self) -> float:
        return max(self.durations)

    @property
    def fits(self) -> bool:
        """Whether p95 is inside the proposed budget; an endpoint without one always fits."""
        return self.p95 <= BUDGET_MS.get(self.name, float("inf"))


def percentile(values: Sequence[float], share: float) -> float:
    """Nearest-rank percentile: the smallest value that ``share`` of the sample does not exceed.

    ``math.ceil`` and not ``round``: on an even rank the banker's rounding of ``round`` would
    step one value too far, and a p95 of twenty calls would report the maximum.
    """
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil(share * len(ordered))))
    return ordered[rank - 1]


class QueryCounter:
    """Counts the SQL statements the engine sends; the sequential phase reads it per request.

    ``SET LOCAL ROLE`` and the two ``set_config`` of ADR-008 are counted too: a scoped request
    really does pay for them, and a number that hid them would mislead the reader of the table.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self.total = 0
        self._read = 0
        event.listen(engine.sync_engine, "before_cursor_execute", self._count)

    def _count(self, *_: Any) -> None:
        self.total += 1

    def taken(self) -> int:
        """Statements sent since the previous call."""
        taken = self.total - self._read
        self._read = self.total
        return taken


def token_check_ms() -> float:
    """Milliseconds one check of a device token costs on this machine (ADR-005).

    ``current_device`` runs it in the event loop before any query, so on one worker these
    milliseconds are serial and sit inside every batch number below. They used to be argon2id
    — tens of them per request of every agent; the check is a sha256 comparison now, and this
    is the number that says so. ``argon2_check_ms`` measures what it replaced, on the same
    machine, so the two can be printed side by side.
    """
    secret = new_device_secret()
    hashed = hash_token(secret)
    taken = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        verify_token(secret, hashed)
        taken.append((time.perf_counter() - started) * 1000)
    return statistics.median(taken)


def argon2_check_ms() -> float:
    """Milliseconds the argon2id check of the same token used to cost (ТЗ п. 3, T-56)."""
    secret = new_device_secret()
    hashed = hash_secret(secret)
    taken = []
    for _ in range(5):
        started = time.perf_counter()
        verify_secret(secret, hashed)
        taken.append((time.perf_counter() - started) * 1000)
    return statistics.median(taken)


@pytest.fixture
async def load_engine() -> AsyncIterator[AsyncEngine]:
    """Engine repeating the pool of a deployment: ``POOL`` + ``OVERFLOW``, with pre-ping.

    One deliberate difference: ``pool_timeout`` is raised from the default 30 seconds, because
    in the concurrent phase a thousand requests queue for fifteen connections on purpose.
    """
    engine = create_async_engine(
        DSN, pool_size=POOL, max_overflow=OVERFLOW, pool_pre_ping=True, pool_timeout=300
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def load_sessions(load_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory of the run: one session per request, committed by the endpoint itself."""
    return async_sessionmaker(load_engine, expire_on_commit=False)


@pytest.fixture
async def load_client(
    load_engine: AsyncEngine, load_sessions: async_sessionmaker[AsyncSession]
) -> AsyncIterator[tuple[AsyncClient, QueryCounter]]:
    """The application over ASGI on the filled database, with nothing of the path switched off.

    The rate limit of T-51 stays on. It counts per device (``rl:device:<id>``,
    ``app/core/ratelimit.py``), so a thousand agents sending one batch each never reach it,
    and its round trip to Redis is part of every real agent request — Redis has to be up
    (``make up``); a counter that does not answer lets the request through with a warning.
    Only ``enqueue_detection`` is silenced, by the autouse fixture of ``conftest.py``.
    """
    async with load_sessions() as probe:
        if await probe.get(SystemSettings, 1) is None:
            pytest.skip("в базе нет строки settings: сначала make seed")

    async def request_session() -> AsyncIterator[AsyncSession]:
        async with load_sessions() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = request_session
    # Not a cost inside the numbers: of the four endpoints measured none writes an audit row —
    # the three GETs are dropped by method and an accepted batch of the agent is skipped on
    # purpose (``app/auth/audit.py``). The factory is set so that a *refused* request, which is
    # audited, writes into the database under load and not into the one ``.env`` points at.
    application.state.audit_sessions = load_sessions
    counter = QueryCounter(load_engine)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver", timeout=600) as c:
        yield c, counter


@pytest.fixture
async def panel_headers(load_sessions: async_sessionmaker[AsyncSession]) -> dict[str, str]:
    """``Authorization`` of an administrator of the filled database: the widest scope there is.

    The token is signed with the key the application in this process reads, so the run needs no
    server to be up; ``make seed`` creates ``admin@example.kz`` (AGENTS.md §7).
    """
    query = select(User).where(User.role == "admin", User.is_active).limit(1)
    async with load_sessions() as session:
        admin = (await session.scalars(query)).one_or_none()
    if admin is None:
        pytest.skip("в базе нет активного администратора: сначала make seed")
    return bearer(admin)


@asynccontextmanager
async def load_devices(
    sessions: async_sessionmaker[AsyncSession], count: int
) -> AsyncIterator[list[str]]:
    """``count`` devices of the run on existing monitoring points; yields their tokens.

    They are registered the way T-14 does it — only the sha256 hash of the secret is stored
    (ADR-005, ``app/core/security.py``). One secret is hashed once and the same hash goes to
    every device: what a request verifies costs exactly the same either way.

    The cleanup runs in ``finally``, which a killed interpreter never reaches. A run cut short
    leaves ``load-…`` devices and their measurements on live schools, where they count towards
    the status of the school (ADR-004, T-16); the SQL that removes them is in §2 of the document.
    """
    secret = new_device_secret()
    token_hash = hash_token(secret)
    async with sessions() as session:
        points = list(await session.scalars(select(MonitoringPoint.id)))
        if not points:
            pytest.skip("в базе нет точек мониторинга: сначала make seed и make simulate")
        devices = [
            Device(
                device_uid=f"load-{uuid.uuid4()}",
                monitoring_point_id=points[number % len(points)],
                token_hash=token_hash,
                agent_version="0.1.0",
            )
            for number in range(count)
        ]
        session.add_all(devices)
        await session.flush()
        ids = [device.id for device in devices]
        tokens = [format_device_token(device.id, secret) for device in devices]
        await session.commit()
    try:
        yield tokens
    finally:
        async with sessions() as session:
            # Everything that points at a device, then the device: measurements, heartbeats
            # and outages are the three foreign keys of ``devices`` (T-02).
            await session.execute(delete(Measurement).where(Measurement.device_id.in_(ids)))
            await session.execute(delete(Heartbeat).where(Heartbeat.device_id.in_(ids)))
            await session.execute(delete(Outage).where(Outage.device_id.in_(ids)))
            await session.execute(delete(Device).where(Device.id.in_(ids)))
            await session.commit()


def record(measured_at: datetime) -> dict[str, Any]:
    """One measurement as an agent sends it (``MeasurementCreate`` of app/schemas/agent.py)."""
    return {
        "measurement_uuid": str(uuid.uuid4()),
        "measured_at": measured_at.isoformat(),
        "connection_status": "online",
        "download_mbps": 94.5,
        "upload_mbps": 88.1,
        "ping_ms": 12.0,
        "jitter_ms": 1.5,
        "packet_loss_pct": 0.0,
        "duration_s": 21.4,
        "iface_type": "ethernet",
        "agent_version": "0.1.0",
    }


def batch(items: int) -> dict[str, Any]:
    """Body of a resent queue: ``items`` fresh records dated inside the window of ADR-006."""
    newest = datetime.now(UTC) - timedelta(minutes=1)
    return {"items": [record(newest - timedelta(minutes=i)) for i in range(items)]}


async def measure(
    client: AsyncClient, counter: QueryCounter, call: Call, headers: dict[str, str]
) -> Timing:
    """Call the endpoint ``REPEATS`` times, one at a time, and collect what it cost."""
    durations: list[float] = []
    statements = 0
    # The first call of a fresh pool pays for its connections and plans; a running server
    # does not, so it is made and thrown away.
    await client.request(call.method, call.url, headers=headers, json=payload(call))
    for _ in range(REPEATS):
        body = payload(call)
        counter.taken()
        started = time.perf_counter()
        response = await client.request(call.method, call.url, headers=headers, json=body)
        durations.append((time.perf_counter() - started) * 1000)
        statements = counter.taken()
        assert response.status_code == 200, f"{call.name}: {response.status_code}"
    return Timing(name=call.name, durations=durations, statements=statements)


def payload(call: Call) -> dict[str, Any] | None:
    """Fresh body of the call; a GET has none, a batch needs new uuids every time."""
    return batch(BATCH_ITEMS) if call.body else None


def report(timings: Sequence[Timing], check_ms: float) -> None:
    """Print the table docs/product/load-test.md asks to paste into docs/worklog.md."""
    print(f"\nЗапросов на эндпоинт: {REPEATS}. Пул: {POOL} + {OVERFLOW} сверх лимита.")
    print(f"{'Эндпоинт':<38}{'p50':>8}{'p95':>8}{'max':>8}{'SQL':>6}  Вердикт")
    for timing in timings:
        verdict = "норма" if timing.fits else "медленно"
        print(
            f"{timing.name:<38}{timing.p50:>8.0f}{timing.p95:>8.0f}"
            f"{timing.worst:>8.0f}{timing.statements:>6}  {verdict}"
        )
    print(
        f"Проверка токена: {check_ms:.3f} мс в каждом ответе батча "
        f"(argon2 на этой же машине: {argon2_check_ms():.0f} мс)."
    )
    slow = [timing.name for timing in timings if not timing.fits]
    if slow:
        print(f"Вне предложенного бюджета: {', '.join(slow)}. См. docs/product/load-test.md.")


async def test_endpoint_latency(
    load_client: tuple[AsyncClient, QueryCounter],
    load_sessions: async_sessionmaker[AsyncSession],
    panel_headers: dict[str, str],
) -> None:
    """Answer times of the four endpoints of T-56 on the data that is in the database.

    The worst case of each on purpose: the map without a lower bound of the period, the summary
    over its default 24 hours, analytics over a month by district — the one that reads
    ``m_daily``, the heatmap of ``m_hourly`` and the heartbeats of the whole month (T-27) — and
    the batch of an agent that has been offline.
    """
    client, counter = load_client
    panel = [
        Call("GET /api/map/schools", "GET", "/api/map/schools"),
        Call("GET /api/dashboard/summary", "GET", "/api/dashboard/summary"),
        Call(
            "GET /api/analytics (month, district)",
            "GET",
            "/api/analytics?level=district&period=month",
        ),
    ]
    timings = [await measure(client, counter, call, panel_headers) for call in panel]
    # The device of the batch is registered only now: a computer that has never reported would
    # otherwise be counted by the status of its school and move the answer of the map and of
    # the summary while they are being measured (ADR-004, T-16).
    agent = Call("POST /api/measurements/batch", "POST", "/api/measurements/batch", body=True)
    async with load_devices(load_sessions, 1) as tokens:
        device = {"Authorization": f"Device {tokens[0]}"}
        timings.append(await measure(client, counter, agent, device))
    report(timings, token_check_ms())
    if STRICT:
        assert [timing.name for timing in timings if not timing.fits] == []


async def test_concurrent_batches(
    load_client: tuple[AsyncClient, QueryCounter],
    load_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """``DEVICES`` agents resend their queue at once and every record is accepted (ТЗ п. 3).

    This is the moment of ADR-006 the intake is built for: the connection comes back and every
    school sends what it saved while it was down. Nothing may be refused and nothing lost, so
    the check is on the answers; the clock is only reported, and the report says how much of it
    is the token check rather than the database.
    """
    client, _ = load_client
    check_ms = token_check_ms()
    async with load_devices(load_sessions, DEVICES) as tokens:

        async def send(token: str) -> Response:
            return await client.post(
                "/api/measurements/batch",
                headers={"Authorization": f"Device {token}"},
                json=batch(BATCH_ITEMS),
            )

        started = time.perf_counter()
        sent = [send(token) for token in tokens]
        results = await asyncio.gather(*sent, return_exceptions=True)
        elapsed = time.perf_counter() - started

        broken = [result for result in results if isinstance(result, BaseException)]
        assert not broken, f"батчи не дошли: {len(broken)}, первый — {broken[0]!r}"
        answers = [result for result in results if not isinstance(result, BaseException)]
        refused = [answer.status_code for answer in answers if answer.status_code != 200]
        assert not refused, f"батчи отклонены: {len(refused)}, коды — {sorted(set(refused))}"
        accepted = [item for answer in answers for item in answer.json()["results"]]
        stored = sum(1 for item in accepted if item["status"] == 201)

    print(
        f"\nОдновременных батчей: {DEVICES} по {BATCH_ITEMS} записей. "
        f"Время: {elapsed:.1f} с. Принято записей: {stored} из {DEVICES * BATCH_ITEMS}."
    )
    print(
        f"Из них проверка токенов: около {DEVICES * check_ms / 1000:.2f} с "
        f"(argon2 стоил бы {DEVICES * argon2_check_ms() / 1000:.0f} с на этом же прогоне)."
    )
    assert stored == DEVICES * BATCH_ITEMS
