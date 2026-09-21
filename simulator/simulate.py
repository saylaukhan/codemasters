"""Agent simulator: 350 schools, 1000 computers, the history the server accepts (T-55).

plan.md §15 (demo 7) and ТЗ п. 3: the map, the overview and the analytics must stay fast on the
data of a whole region, so this generator fills a local installation through the same API the
real agent speaks (ADR-006) — an installation code, ``POST /api/devices/register``, batches of
``POST /api/measurements/batch``, heartbeats and ``POST /api/outages``. Nothing is written into
the database directly: what the server refuses from an agent the simulator must not be able to
write either.

Two promises hold the generator together. The profiles are pure functions of the device and the
moment, so a rerun produces the same numbers and the same ``measurement_uuid``, and the server
answers a repeat with 409 instead of doubling the history (ADR-006, T-51). And nothing about a
school is hard-coded here (ТЗ п. 11, п. 20; ADR-004): the thresholds, the schedule slots and the
timezone come from ``GET /api/agent/config``, the contract speeds from
``GET /api/schools/{id}/lines``, the rooms of the monitoring points from
``GET /api/schools/{id}/points``, the schools themselves from the seed of T-04. The constants
below are limits of the contract (how large a batch may be, how far back a moment may point) and
fallbacks used only by ``--dry-run`` and the tests, which have no server to ask. The one
exception is ``UNSTABLE_OVER``: the configuration of an agent carries no
``unstable_deviation_pct``, so how far «Нестабильно» goes past a limit is decided here — the
only assumption about the thresholds the generator makes, and README names it.

Two limits the demo data live with, both written down in README: the server refuses a
measurement older than the queue of an agent (31 days, ADR-006), so «3 месяца» of T-55 cannot be
filled through this API at all; and the statuses of the schools hold only as long as the
computers count as alive, which is one ``offline_after_s`` after the run ends.

Standard library only: the simulator is started by ``make simulate`` with the interpreter of
``backend/.venv``, but it must not depend on anything installed there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from datetime import time as clock
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_SCHOOLS = 350
DEFAULT_DEVICES = 1000
DEFAULT_DAYS = 90
DEFAULT_API = "http://localhost:8000"
DEFAULT_ADMIN_EMAIL = "admin@example.kz"
DEFAULT_WORKERS = 8

# The rate limit of registration is counted per address (agent_register_rate_limit, 20 per
# minute by default), so the pace is set here instead of waiting for 429 on every request.
DEFAULT_REGISTER_RATE = 20

# How many device tokens are tried before the configuration of the server is declared missing.
CONFIG_ATTEMPTS = 5

AGENT_VERSION = "0.1.0-sim"
USER_AGENT = f"vko-agent-simulator/{AGENT_VERSION}"
SPEEDTEST_SERVER = "simulator/librespeed"

# Limits of the server the generator must never cross (backend/app/schemas/agent.py, T-51).
MAX_BATCH_SIZE = 100
MAX_SPEED_MBPS = 10_000.0
MAX_LATENCY_MS = 60_000.0
MAX_LOSS_PCT = 100.0
MAX_DURATION_S = 3600.0

# The queue of an agent holds 31 days (MAX_QUEUE_AGE, ADR-006): a measurement dated earlier is
# refused with 422, whatever ``--days`` asks for. A day of margin keeps the oldest record inside
# the window while a long run is still going.
#
# The «3 месяца истории» of T-55 therefore cannot be filled through the API of the agent at all:
# the requirement of the task and the contract of the server contradict each other, and the
# simulator says so out loud on every run instead of quietly shortening the history. Filling
# 90 days means writing into the database past the API — a decision of the lead, not of this
# file (see simulator/README.md, «Ограничения»).
HISTORY_WINDOW_DAYS = 30

# Namespace of the simulated measurements: derived, not invented, so it is the same everywhere.
SIM_NAMESPACE = uuid5(NAMESPACE_URL, "vko-monitor/simulator")

# Addresses of RFC 5737 (TEST-NET-3): documentation range, never a real school address.
EXTERNAL_IP_PREFIX = "203.0.113."

PROFILE_NORMAL = "normal"
PROFILE_PEAK = "peak"
PROFILE_UNSTABLE = "unstable"
PROFILE_CRITICAL = "critical"
PROFILE_OUTAGE = "outage"
PROFILE_CONTRACT = "contract"

PROFILE_TITLES = {
    PROFILE_NORMAL: "норма",
    PROFILE_PEAK: "деградация по часам",
    PROFILE_UNSTABLE: "нестабильно",
    PROFILE_CRITICAL: "критично",
    PROFILE_OUTAGE: "простой",
    PROFILE_CONTRACT: "ниже договора",
}

# Profiles of the schools in a fixed order: the first six give one school of every status of
# ТЗ п. 13 even on a tiny run, the rest set the share — a region where most schools are fine.
PROFILE_CYCLE = (
    PROFILE_NORMAL,
    PROFILE_PEAK,
    PROFILE_UNSTABLE,
    PROFILE_CRITICAL,
    PROFILE_OUTAGE,
    PROFILE_CONTRACT,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_PEAK,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_UNSTABLE,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_PEAK,
    PROFILE_NORMAL,
    PROFILE_NORMAL,
    PROFILE_CRITICAL,
)

# Hours of the local day the «деградация по часам» profile falls apart in: the lessons start,
# the whole school goes online, the line sags and recovers after the last lesson.
PEAK_FROM_HOUR = 11
PEAK_WORST_HOUR = 13
PEAK_UNTIL_HOUR = 16

# How far past its limit one metric goes to read «Нестабильно»: 8–20 % over it. This is the one
# threshold rule the simulator cannot ask the server about — ``GET /api/agent/config`` returns
# ``ThresholdValues`` without ``unstable_deviation_pct`` — so the band is fixed here to fit the
# 30 % of «Решения по умолчанию». Lowered below 8 % in the admin panel (ТЗ п. 11), the profile
# «нестабильно» starts reading «Критично»: it is the only assumption about the thresholds the
# generator makes, and README names it under «Ограничения».
UNSTABLE_OVER = (1.08, 1.20)
# «Критично» is two metrics past their limits at once, which holds at any allowed deviation.
CRITICAL_OVER = (1.5, 2.4)

# Share of the computers of a school, second one and further, that measure over Wi-Fi: such a
# measurement rates the air, not the line, and the server keeps it out of the status (ADR-012).
WIFI_SHARE = 0.35

# What the air costs against the cable. The server judges a Wi-Fi measurement like any other
# (app/services/status.py: ``rates_line`` only keeps it out of the status of the school and out
# of the contract), so the penalty stops at the limits: 10 % of headroom on the safe side of
# every threshold. Without that a Wi-Fi computer of a school of the «норма» профиль reads
# «Критично» on its own card, in ``GET /api/devices/{id}/measurements`` and in the export.
WIFI_DOWN_FACTOR = 0.55
WIFI_UP_FACTOR = 0.60
WIFI_PING_FACTOR = 1.60
WIFI_JITTER_FACTOR = 2.00
WIFI_KEEP_PCT = 0.10

# Only ``--dry-run`` and the tests use these: a live run reads them from GET /api/agent/config.
FALLBACK_TIMEZONE = "Asia/Almaty"
FALLBACK_UNSTABLE_DEVIATION_PCT = 30.0


class SimulatorError(Exception):
    """A reason to stop: no server, no credentials, no schools to measure."""


@dataclass(frozen=True)
class Thresholds:
    """Limits one measurement is judged by (ТЗ п. 11, ADR-004)."""

    download_min_mbps: float
    upload_min_mbps: float
    ping_max_ms: float
    jitter_max_ms: float
    packet_loss_max_pct: float

    @classmethod
    def from_config(cls, payload: dict[str, Any]) -> Thresholds:
        """Thresholds of ``GET /api/agent/config``: the agent hard-codes none of them."""
        values = payload["thresholds"]
        return cls(
            download_min_mbps=float(values["download_min_mbps"]),
            upload_min_mbps=float(values["upload_min_mbps"]),
            ping_max_ms=float(values["ping_max_ms"]),
            jitter_max_ms=float(values["jitter_max_ms"]),
            packet_loss_max_pct=float(values["packet_loss_max_pct"]),
        )


@dataclass(frozen=True)
class Slot:
    """Measurement window of the schedule; the moment inside it is picked per computer."""

    start: clock
    end: clock


# Thresholds and slots of «Решения по умолчанию» — the shape the migration of T-17 creates.
FALLBACK_THRESHOLDS = Thresholds(
    download_min_mbps=20.0,
    upload_min_mbps=20.0,
    ping_max_ms=100.0,
    jitter_max_ms=30.0,
    packet_loss_max_pct=2.0,
)
FALLBACK_SLOTS = (
    Slot(clock(8, 30), clock(9, 0)),
    Slot(clock(11, 0), clock(11, 30)),
    Slot(clock(13, 30), clock(14, 0)),
    Slot(clock(16, 0), clock(16, 30)),
)


@dataclass(frozen=True)
class SimSchool:
    """School of the seed the simulator measures: its profile and what its contract promises."""

    school_id: int
    school_code: str
    full_name: str
    index: int
    profile: str = PROFILE_NORMAL
    contract_down_mbps: float | None = None
    contract_up_mbps: float | None = None
    room: str | None = None


@dataclass(frozen=True)
class SimDevice:
    """One simulated computer: everything the profiles need and nothing else."""

    device_uid: str
    hostname: str
    school_id: int
    school_code: str
    profile: str
    wifi: bool = False
    contract_down_mbps: float | None = None
    contract_up_mbps: float | None = None
    external_ip: str = f"{EXTERNAL_IP_PREFIX}1"
    room: str | None = None


# --- Deterministic noise ---------------------------------------------------------------------


def noise(*parts: object) -> float:
    """A number in ``[0, 1)`` decided by ``parts`` alone — the same on every run.

    ``random`` would give a different history to every run and break both the idempotency of
    ``measurement_uuid`` and any test of the profiles, so the spread of the values is taken
    from a hash of what they describe: the computer, the moment and the name of the metric.
    """
    key = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


def spread(low: float, high: float, *parts: object) -> float:
    """Value between ``low`` and ``high`` decided by ``parts``, to two decimals."""
    if high < low:
        low, high = high, low
    return round(low + noise(*parts) * (high - low), 2)


def clamp(value: float, high: float) -> float:
    """Keep a metric inside the range the server accepts (T-51): never below zero, never above."""
    return round(min(max(value, 0.0), high), 2)


def measurement_uuid(device_uid: str, moment: datetime) -> UUID:
    """Idempotency key of a measurement: the computer and the moment decide it (ADR-006).

    A rerun of the simulator sends the same UUID for the same slot, and the server answers 409
    ``duplicate_measurement`` instead of storing the day twice.
    """
    return uuid5(SIM_NAMESPACE, f"{device_uid}|{moment.isoformat()}")


# --- Profiles ---------------------------------------------------------------------------------


def target_quality(profile: str, moment: datetime) -> str:
    """Status of ТЗ п. 13 the profile aims at for this local moment.

    «Деградация по часам» is the only profile that depends on the clock: the line holds in the
    morning, sags when the lessons start and is at its worst in the afternoon.
    """
    if profile == PROFILE_OUTAGE:
        return "offline"
    if profile == PROFILE_UNSTABLE:
        return "unstable"
    if profile == PROFILE_CRITICAL:
        return "critical"
    if profile == PROFILE_PEAK:
        hour = moment.hour
        if hour < PEAK_FROM_HOUR or hour >= PEAK_UNTIL_HOUR:
            return "normal"
        return "critical" if hour >= PEAK_WORST_HOUR else "unstable"
    return "normal"


def healthy_metrics(
    device: SimDevice, moment: datetime, thresholds: Thresholds
) -> dict[str, float]:
    """Numbers of a line that keeps both its thresholds and its contract (ТЗ п. 11, п. 14)."""
    down_floor = max(thresholds.download_min_mbps * 1.4, (device.contract_down_mbps or 0.0) * 1.05)
    up_floor = max(thresholds.upload_min_mbps * 1.4, (device.contract_up_mbps or 0.0) * 1.05)
    return {
        "download_mbps": spread(down_floor, down_floor * 1.35, device.device_uid, moment, "down"),
        "upload_mbps": spread(up_floor, up_floor * 1.3, device.device_uid, moment, "up"),
        "ping_ms": spread(
            thresholds.ping_max_ms * 0.12,
            thresholds.ping_max_ms * 0.40,
            device.device_uid,
            moment,
            "ping",
        ),
        "jitter_ms": spread(
            thresholds.jitter_max_ms * 0.08,
            thresholds.jitter_max_ms * 0.45,
            device.device_uid,
            moment,
            "jitter",
        ),
        "packet_loss_pct": spread(
            0.0, thresholds.packet_loss_max_pct * 0.25, device.device_uid, moment, "loss"
        ),
    }


def degrade(
    metrics: dict[str, float],
    device: SimDevice,
    moment: datetime,
    thresholds: Thresholds,
    *,
    target: str,
) -> dict[str, float]:
    """Push the metrics past their limits exactly as far as the target status needs.

    «Нестабильно» is one metric over its limit by ``UNSTABLE_OVER`` — 8–20 %, which reads as
    unstable while the profile allows a deviation of at least 8 % (see the constant: the
    configuration of the agent does not carry ``unstable_deviation_pct``). «Критично» is two
    metrics past their limits at once, which is critical at any allowed deviation (plan.md §6).
    Latency is what sags first on a school line, so it leads; a profile with a zero latency
    limit has nothing to breach there and the speed is lowered instead.
    """
    spoiled = dict(metrics)
    latency = thresholds.ping_max_ms > 0
    over = UNSTABLE_OVER if target == "unstable" else CRITICAL_OVER
    if latency:
        spoiled["ping_ms"] = spread(
            thresholds.ping_max_ms * over[0],
            thresholds.ping_max_ms * over[1],
            device.device_uid,
            moment,
            "ping-over",
        )
    else:
        share = (2.0 - over[1], 2.0 - over[0])
        spoiled["download_mbps"] = spread(
            thresholds.download_min_mbps * share[0],
            thresholds.download_min_mbps * share[1],
            device.device_uid,
            moment,
            "down-under",
        )
    if target != "critical":
        return spoiled
    # The second breach: loss if the profile allows any, otherwise the speed.
    if thresholds.packet_loss_max_pct > 0:
        spoiled["packet_loss_pct"] = spread(
            thresholds.packet_loss_max_pct * 1.6,
            thresholds.packet_loss_max_pct * 3.0,
            device.device_uid,
            moment,
            "loss-over",
        )
    else:
        spoiled["download_mbps"] = spread(
            thresholds.download_min_mbps * 0.4,
            thresholds.download_min_mbps * 0.7,
            device.device_uid,
            moment,
            "down-under",
        )
    return spoiled


def below_contract(
    metrics: dict[str, float], device: SimDevice, moment: datetime, thresholds: Thresholds
) -> dict[str, float]:
    """Lower the speeds under the contract but keep them over the thresholds (ТЗ п. 14).

    This is the case the panel must show apart from a bad line: the school reads «Норма», and
    the line still never reaches what the provider sold (T-29). A school whose contract is too
    close to the thresholds cannot show it, which is why ``assign_profiles`` does not give this
    profile to one.
    """
    lowered = dict(metrics)
    for metric, limit, contract in (
        ("download_mbps", thresholds.download_min_mbps, device.contract_down_mbps),
        ("upload_mbps", thresholds.upload_min_mbps, device.contract_up_mbps),
    ):
        if not contract:
            continue
        floor = limit * 1.15
        ceiling = max(contract * 0.75, floor * 1.05)
        lowered[metric] = spread(floor, ceiling, device.device_uid, moment, f"contract-{metric}")
    return lowered


def over_the_air(metrics: dict[str, float], thresholds: Thresholds) -> dict[str, float]:
    """The same line measured over Wi-Fi: slower and shakier, but still inside the limits.

    The air loses to the cable, and the server keeps such a measurement out of the status of the
    school and out of the contract (ADR-012) — but it still gives it a status of its own, which
    the card of the computer and the export show. So the penalty is bounded: whatever the
    thresholds are, a Wi-Fi record of a school that is «Норма» stays «Норма», and a profile that
    aims past a limit breaches it afterwards, in ``degrade``.
    """
    slowed = dict(metrics)
    slowed["download_mbps"] = max(
        metrics["download_mbps"] * WIFI_DOWN_FACTOR,
        thresholds.download_min_mbps * (1 + WIFI_KEEP_PCT),
    )
    slowed["upload_mbps"] = max(
        metrics["upload_mbps"] * WIFI_UP_FACTOR,
        thresholds.upload_min_mbps * (1 + WIFI_KEEP_PCT),
    )
    slowed["ping_ms"] = min(
        metrics["ping_ms"] * WIFI_PING_FACTOR,
        thresholds.ping_max_ms * (1 - WIFI_KEEP_PCT),
    )
    slowed["jitter_ms"] = min(
        metrics["jitter_ms"] * WIFI_JITTER_FACTOR,
        thresholds.jitter_max_ms * (1 - WIFI_KEEP_PCT),
    )
    return slowed


def measurement(device: SimDevice, moment: datetime, thresholds: Thresholds) -> dict[str, Any]:
    """One measurement of one computer: the body of ``MeasurementCreate`` (plan.md §5).

    Pure: the device, the moment and the thresholds decide everything, so the same call always
    returns the same record and a test needs neither a server nor a database.
    """
    item: dict[str, Any] = {
        "measurement_uuid": str(measurement_uuid(device.device_uid, moment)),
        "measured_at": moment.isoformat(),
        "agent_version": AGENT_VERSION,
        "external_ip": device.external_ip,
    }
    target = target_quality(device.profile, moment)
    if target == "offline":
        # Nothing was measured: the line was down and the agent only recorded the fact (ТЗ п. 2).
        item["connection_status"] = "offline"
        return item

    # The order matters: the air sags the numbers of a healthy line, and only then the profile
    # pushes what it means to push past the limits. The other way round the Wi-Fi factor would
    # multiply the breach itself and turn «Нестабильно» into «Критично».
    metrics = healthy_metrics(device, moment, thresholds)
    if device.profile == PROFILE_CONTRACT:
        metrics = below_contract(metrics, device, moment, thresholds)
    if device.wifi:
        metrics = over_the_air(metrics, thresholds)
    if target in ("unstable", "critical"):
        metrics = degrade(metrics, device, moment, thresholds, target=target)
    item["iface_type"] = "wifi" if device.wifi else "ethernet"

    item["connection_status"] = "online"
    item["download_mbps"] = clamp(metrics["download_mbps"], MAX_SPEED_MBPS)
    item["upload_mbps"] = clamp(metrics["upload_mbps"], MAX_SPEED_MBPS)
    item["ping_ms"] = clamp(metrics["ping_ms"], MAX_LATENCY_MS)
    item["jitter_ms"] = clamp(metrics["jitter_ms"], MAX_LATENCY_MS)
    item["packet_loss_pct"] = clamp(metrics["packet_loss_pct"], MAX_LOSS_PCT)
    item["duration_s"] = clamp(
        spread(18.0, 26.0, device.device_uid, moment, "duration"), MAX_DURATION_S
    )
    item["server"] = SPEEDTEST_SERVER
    return item


def breaches(item: dict[str, Any], thresholds: Thresholds) -> list[tuple[str, float]]:
    """Metrics of a generated record past their limits, with the deviation in percent.

    A mirror of ``app.services.status.breaches`` (plan.md §6) kept here on purpose: the
    simulator must be able to check its own profiles without importing the backend, and
    ``--dry-run`` prints the verdict next to the status the profile aimed at.
    """
    limits = (
        ("download_mbps", thresholds.download_min_mbps, True),
        ("upload_mbps", thresholds.upload_min_mbps, True),
        ("ping_ms", thresholds.ping_max_ms, False),
        ("jitter_ms", thresholds.jitter_max_ms, False),
        ("packet_loss_pct", thresholds.packet_loss_max_pct, False),
    )
    found = []
    for metric, limit, at_least in limits:
        value = item.get(metric)
        if value is None:
            continue
        past = limit - value if at_least else value - limit
        if past <= 0:
            continue
        found.append((metric, 100 * past / limit if limit else math.inf))
    return found


def expected_quality(
    item: dict[str, Any],
    thresholds: Thresholds,
    *,
    allowed_pct: float = FALLBACK_UNSTABLE_DEVIATION_PCT,
) -> str:
    """Status the server will give this record (ADR-004) — the check of the generator itself."""
    if item.get("connection_status") == "offline":
        return "offline"
    found = breaches(item, thresholds)
    if not found:
        return "normal"
    gross = [metric for metric, deviation in found if deviation > allowed_pct]
    return "unstable" if len(found) == 1 and not gross else "critical"


# --- Schedule ----------------------------------------------------------------------------------


def zone(name: str) -> tzinfo:
    """Timezone of the schedule; a host without the tz database still gets the right offset."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        warn(f"пояс {name} не найден в системе, беру постоянный UTC+05:00")
        return timezone(timedelta(hours=5), name)


def slot_moments(device_uid: str, day: date, slots: Sequence[Slot], tz: tzinfo) -> list[datetime]:
    """Moments a computer measures at on that day: one inside every slot (plan.md §4.2).

    The offset inside a slot is the jitter of the real agent, but taken from the hash of the
    computer and the day, so a rerun asks about exactly the same moments.
    """
    moments = []
    for index, slot in enumerate(slots):
        start = datetime.combine(day, slot.start, tzinfo=tz)
        end = datetime.combine(day, slot.end, tzinfo=tz)
        if end <= start:
            end = start + timedelta(minutes=30)
        span = (end - start).total_seconds()
        offset = int(noise(device_uid, day.isoformat(), index, "slot") * span)
        moments.append(start + timedelta(seconds=offset))
    return moments


def history_days(days: int, now: datetime, tz: tzinfo) -> list[date]:
    """Days to fill, oldest first: everything the queue window of the server still accepts."""
    today = now.astimezone(tz).date()
    depth = min(days, HISTORY_WINDOW_DAYS)
    return [today - timedelta(days=step) for step in range(depth - 1, -1, -1)]


def history_warning(asked: int, given: int) -> str:
    """Why the history is shorter than asked — said before the run, not after it.

    The requirement of T-55 («3 месяца истории», ``make simulate days=90``) and the contract of
    the server (``MAX_QUEUE_AGE`` — 31 days, ADR-006) contradict each other, and the simulator
    is on the side of the contract: it writes only what an agent may send.
    """
    return (
        f"История будет за {given} сут., а не за {asked}: сервер отклоняет замер старше очереди "
        "агента (31 сут., ADR-006), и через API агента «3 месяца» из T-55 не залить. "
        "Прямая запись в БД мимо API — решение лида; см. simulator/README.md, «Ограничения»."
    )


def device_measurements(
    device: SimDevice,
    days: Sequence[date],
    slots: Sequence[Slot],
    tz: tzinfo,
    thresholds: Thresholds,
    now: datetime,
) -> list[dict[str, Any]]:
    """The whole history of one computer: every slot of every day that has already happened."""
    items = []
    for day in days:
        for moment in slot_moments(device.device_uid, day, slots, tz):
            if moment > now:
                continue
            items.append(measurement(device, moment, thresholds))
    return items


def device_outages(
    device: SimDevice, days: Sequence[date], slots: Sequence[Slot], tz: tzinfo, now: datetime
) -> list[dict[str, str]]:
    """Periods without connection of a computer of the «простой» profile (ТЗ п. 2, T-12).

    One period a day, from the first slot to the last: the agent records what it could not
    measure and sends it when the line is back (ADR-006).
    """
    if device.profile != PROFILE_OUTAGE or not slots:
        return []
    periods = []
    for day in days:
        started = datetime.combine(day, slots[0].start, tzinfo=tz)
        ended = datetime.combine(day, slots[-1].end, tzinfo=tz)
        if started > now:
            continue
        periods.append({"started_at": started.isoformat(), "ended_at": min(ended, now).isoformat()})
    return periods


def chunks(items: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    """Split a list into batches the server accepts: at most ``MAX_BATCH_SIZE`` items (ADR-006)."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


# --- Schools and devices -------------------------------------------------------------------


def assign_profiles(schools: Sequence[SimSchool], thresholds: Thresholds) -> list[SimSchool]:
    """Give every school its profile, in the fixed order of ``PROFILE_CYCLE``.

    One correction afterwards: «ниже договора» needs a contract far enough above the thresholds
    for the line to stay «Норма» while missing what was sold, so such a school swaps profiles
    with the first plain one that can show it (T-29). Deterministic, so a rerun measures the
    same school the same way.
    """
    assigned = [
        SimSchool(
            school_id=school.school_id,
            school_code=school.school_code,
            full_name=school.full_name,
            index=school.index,
            profile=PROFILE_CYCLE[index % len(PROFILE_CYCLE)],
            contract_down_mbps=school.contract_down_mbps,
            contract_up_mbps=school.contract_up_mbps,
            room=school.room,
        )
        for index, school in enumerate(schools)
    ]
    needed = thresholds.download_min_mbps * 2
    fits = [
        index
        for index, school in enumerate(assigned)
        if school.profile == PROFILE_NORMAL and (school.contract_down_mbps or 0.0) >= needed
    ]
    spare = iter(fits)
    for index, school in enumerate(assigned):
        if school.profile != PROFILE_CONTRACT or (school.contract_down_mbps or 0.0) >= needed:
            continue
        other = next(spare, None)
        if other is None:
            warn("нет школы с договором выше порогов: профиль «ниже договора» пропущен")
            assigned[index] = SimSchool(**{**school.__dict__, "profile": PROFILE_NORMAL})
            continue
        assigned[index], assigned[other] = (
            SimSchool(**{**school.__dict__, "profile": PROFILE_NORMAL}),
            SimSchool(**{**assigned[other].__dict__, "profile": PROFILE_CONTRACT}),
        )
    return assigned


def build_devices(schools: Sequence[SimSchool], count: int) -> list[SimDevice]:
    """Spread the computers over the schools round-robin: every school gets at least one.

    ``device_uid`` is the identity of a computer for the server (ADR-005), so it is derived
    from the School ID and the number of the computer and never changes between runs.
    """
    if not schools:
        raise SimulatorError("нет школ: выполните make seed")
    devices = []
    for index in range(count):
        school = schools[index % len(schools)]
        number = index // len(schools) + 1
        device_uid = f"sim-{school.school_code}-{number:02d}"
        wifi = number > 1 and noise(device_uid, "wifi") < WIFI_SHARE
        devices.append(
            SimDevice(
                device_uid=device_uid,
                hostname=f"PC-{school.school_code}-{number:02d}",
                school_id=school.school_id,
                school_code=school.school_code,
                profile=school.profile,
                wifi=wifi,
                contract_down_mbps=school.contract_down_mbps,
                contract_up_mbps=school.contract_up_mbps,
                external_ip=f"{EXTERNAL_IP_PREFIX}{1 + school.index % 254}",
                room=school.room,
            )
        )
    return devices


# --- HTTP ---------------------------------------------------------------------------------


@dataclass
class Response:
    """Answer of the server: the status and the decoded body (``problem+json`` included)."""

    status: int
    payload: Any = None

    @property
    def detail(self) -> str:
        if isinstance(self.payload, dict):
            return str(self.payload.get("detail") or self.payload.get("title") or self.payload)
        return str(self.payload)


class Api:
    """Thin HTTP client over ``urllib``: retries what is worth retrying and decodes the rest."""

    def __init__(self, base_url: str, *, timeout: float = 30.0, retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def call(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        headers: dict[str, str] | None = None,
        retries: int | None = None,
    ) -> Response:
        """One request; 429 waits out ``Retry-After``, 5xx backs off, 4xx comes back as is."""
        attempts = self.retries if retries is None else retries
        data = json.dumps(body).encode("utf-8") if body is not None else None
        head = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if data is not None:
            head["Content-Type"] = "application/json"
        head.update(headers or {})
        for attempt in range(attempts + 1):
            request = urllib.request.Request(
                self.base_url + path, data=data, headers=head, method=method
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                    return Response(answer.status, decode(answer.read()))
            except urllib.error.HTTPError as error:
                response = Response(error.code, decode(error.read()))
                if attempt >= attempts:
                    return response
                if error.code == 429:
                    time.sleep(retry_after(error.headers.get("Retry-After")))
                    continue
                if error.code >= 500:
                    time.sleep(2.0**attempt)
                    continue
                return response
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt >= attempts:
                    raise SimulatorError(
                        f"{method} {path}: нет связи с сервером ({error})"
                    ) from error
                time.sleep(2.0**attempt)
        raise SimulatorError(f"{method} {path}: запрос не удался")


def decode(raw: bytes) -> Any:
    """Body of an answer: JSON where there is JSON, text where there is not, ``None`` for 204."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")


def retry_after(value: str | None) -> float:
    """Seconds the server asked to wait; a missing or broken header means a second."""
    try:
        return max(1.0, float(value or 1.0))
    except ValueError:
        return 1.0


class AdminSession:
    """Panel session of the administrator: the access token lives 15 minutes and is renewed."""

    def __init__(self, api: Api, email: str, password: str) -> None:
        self.api = api
        self.email = email
        self.password = password
        self.token: str | None = None
        self.lock = threading.Lock()

    def login(self) -> None:
        response = self.api.call(
            "POST", "/api/auth/login", body={"email": self.email, "password": self.password}
        )
        if response.status != 200:
            raise SimulatorError(f"вход {self.email}: {response.status} {response.detail}")
        with self.lock:
            self.token = response.payload["access_token"]

    def request(self, method: str, path: str, *, body: Any = None) -> Response:
        """Request with the access token; an expired one is exchanged for a new one once."""
        if self.token is None:
            self.login()
        response = self.api.call(
            method, path, body=body, headers={"Authorization": f"Bearer {self.token}"}
        )
        if response.status != 401:
            return response
        self.login()
        return self.api.call(
            method, path, body=body, headers={"Authorization": f"Bearer {self.token}"}
        )


def device_headers(token: str) -> dict[str, str]:
    """Header of the agent: ``Authorization: Device <device_id>.<secret>`` (ADR-005)."""
    return {"Authorization": f"Device {token}"}


# --- State ----------------------------------------------------------------------------------


def default_state_path() -> Path:
    """Where the credentials of the simulated computers live: beside the script, out of git.

    ``simulator/data/`` is covered by the ``data/`` rule of ``.gitignore``, and the file holds
    device tokens, so it is written for its owner only — as the agent keeps its own (ADR-005).
    """
    return Path(__file__).resolve().parent / "data" / "state.json"


def load_state(path: Path) -> dict[str, Any]:
    """Registrations of the previous runs; anything unreadable starts an empty state."""
    empty: dict[str, Any] = {"version": 1, "devices": {}, "schools": {}, "rooms": {}}
    try:
        state = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(state, dict):
        return empty
    state.setdefault("devices", {})
    state.setdefault("schools", {})
    state.setdefault("rooms", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Write the state atomically and keep it readable by its owner only (tokens inside)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    # The permissions are set before the tokens are written, not after: otherwise the file lies
    # readable by everyone for as long as the write takes.
    temporary.touch(mode=0o600, exist_ok=True)
    os.chmod(temporary, 0o600)
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
    temporary.replace(path)


# --- Output -----------------------------------------------------------------------------------


def say(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def warn(message: str) -> None:
    sys.stderr.write(message + "\n")


@dataclass
class Counters:
    """What the run has done so far; printed as progress and as the final report."""

    stored: int = 0
    duplicates: int = 0
    failed: int = 0
    devices_done: int = 0
    outages: int = 0
    heartbeats: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, **values: int) -> None:
        with self.lock:
            for name, value in values.items():
                setattr(self, name, getattr(self, name) + value)


# --- Steps of a run ---------------------------------------------------------------------------


def fetch_schools(admin: AdminSession, limit: int) -> list[SimSchool]:
    """Schools of the seed (T-04), ordered by School ID so a rerun picks the same ones."""
    collected: list[dict[str, Any]] = []
    page = 1
    while len(collected) < limit:
        query = urllib.parse.urlencode(
            {"page": page, "page_size": 100, "sort": "school_code", "is_active": "true"}
        )
        response = admin.request("GET", f"/api/schools?{query}")
        if response.status != 200:
            raise SimulatorError(f"список школ: {response.status} {response.detail}")
        items = response.payload["items"]
        if not items:
            break
        collected.extend(items)
        if len(collected) >= response.payload["total"]:
            break
        page += 1
    if not collected:
        raise SimulatorError("в базе нет школ: выполните make seed")
    return [
        SimSchool(
            school_id=item["id"],
            school_code=item["school_code"],
            full_name=item["full_name"],
            index=index,
        )
        for index, item in enumerate(collected[:limit])
    ]


def fetch_contracts(
    admin: AdminSession, schools: Sequence[SimSchool], state: dict[str, Any], workers: int
) -> list[SimSchool]:
    """Contract speeds of the main line of every school (ТЗ п. 14); cached in the state file."""
    cached: dict[str, Any] = state["schools"]

    def one(school: SimSchool) -> SimSchool:
        known = cached.get(str(school.school_id))
        if known is None:
            response = admin.request("GET", f"/api/schools/{school.school_id}/lines")
            if response.status != 200:
                warn(f"{school.school_code}: линии не прочитаны ({response.status})")
                known = {"contract_down_mbps": None, "contract_up_mbps": None}
            else:
                main = next(
                    (line for line in response.payload["items"] if line["status"] == "main"), None
                )
                known = {
                    "contract_down_mbps": (main or {}).get("contract_down_mbps"),
                    "contract_up_mbps": (main or {}).get("contract_up_mbps"),
                }
            cached[str(school.school_id)] = known
        return SimSchool(
            school_id=school.school_id,
            school_code=school.school_code,
            full_name=school.full_name,
            index=school.index,
            contract_down_mbps=known.get("contract_down_mbps"),
            contract_up_mbps=known.get("contract_up_mbps"),
            room=school.room,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, schools))


def room_of(school: SimSchool) -> str:
    """Room of a school the simulator writes when the point of the seed has none.

    Decided by the code of the school, so a rerun names the same room and the computers keep
    landing on the same monitoring point.
    """
    return str(201 + int(noise(school.school_code, "room") * 20))


def point_room(admin: AdminSession, school: SimSchool) -> str | None:
    """Room of the primary monitoring point of the school, written there if it is empty.

    Without it the column «Кабинет» of the export stays empty on the demo data (ТЗ п. 9): the
    seed of T-04 creates a point with a name and no room, and an agent cannot fill it —
    ``POST /api/devices/register`` only chooses a point by the room, it never creates one
    (ADR-005). So the room is set the way a person would set it, through the panel API, and the
    computers of the school then register into that same point. A room a person has already
    written is kept as it is.
    """
    response = admin.request("GET", f"/api/schools/{school.school_id}/points")
    if response.status != 200:
        warn(f"{school.school_code}: точки мониторинга не прочитаны ({response.status})")
        return None
    points = response.payload["items"]
    if not points:
        warn(f"{school.school_code}: нет точки мониторинга — ПК школы не зарегистрируются")
        return None
    point = points[0]
    if point["room"]:
        return str(point["room"])
    room = room_of(school)
    written = admin.request(
        "PATCH",
        f"/api/schools/{school.school_id}/points/{point['id']}",
        body={"room": room},
    )
    if written.status != 200:
        warn(f"{school.school_code}: кабинет не записан ({written.status} {written.detail})")
        return None
    return room


def fetch_rooms(
    admin: AdminSession, schools: Sequence[SimSchool], state: dict[str, Any], workers: int
) -> list[SimSchool]:
    """Rooms of the monitoring points (ТЗ п. 9, ТЗ п. 10); cached in the state file."""
    cached: dict[str, Any] = state["rooms"]

    def one(school: SimSchool) -> SimSchool:
        known = cached.get(str(school.school_id))
        if known is None:
            known = point_room(admin, school)
            if known is None:
                return school
            cached[str(school.school_id)] = known
        return SimSchool(**{**school.__dict__, "room": str(known)})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, schools))


def register_devices(
    api: Api,
    admin: AdminSession,
    devices: Sequence[SimDevice],
    state: dict[str, Any],
    path: Path,
    rate: int,
) -> None:
    """Register what is not registered yet: one installation code per computer (ADR-005).

    Sequential on purpose: the server counts the codes per address
    (``agent_register_rate_limit``), so the pace is kept here instead of collecting 429. What is
    already in the state file is skipped, which is what makes a rerun cheap.
    """
    known = state["devices"]
    missing = [device for device in devices if device.device_uid not in known]
    if not missing:
        say(f"Регистрация: все {len(devices)} ПК уже зарегистрированы")
        return
    pause = 60.0 / rate if rate > 0 else 0.0
    say(f"Регистрация: {len(missing)} ПК, примерно {math.ceil(len(missing) * pause / 60)} мин")
    for number, device in enumerate(missing, start=1):
        issued = admin.request(
            "POST", "/api/devices/enrollment-codes", body={"school_id": device.school_id}
        )
        if issued.status != 201:
            warn(f"{device.device_uid}: код не выдан ({issued.status} {issued.detail})")
            continue
        response = api.call(
            "POST",
            "/api/devices/register",
            body={
                "enrollment_code": issued.payload["code"],
                "device_uid": device.device_uid,
                "hostname": device.hostname,
                "os": "Windows 11 Pro (симулятор)",
                "agent_version": AGENT_VERSION,
                # The room binds the computer to the point of its school, and the export reads
                # the room of that point (ТЗ п. 9, ADR-005).
                "room": device.room,
            },
            retries=6,
        )
        if response.status != 201:
            warn(f"{device.device_uid}: регистрация {response.status} {response.detail}")
            continue
        known[device.device_uid] = {
            "device_id": response.payload["device_id"],
            "token": response.payload["device_token"],
            "school_id": device.school_id,
            "school_code": device.school_code,
        }
        if number % 25 == 0 or number == len(missing):
            say(f"  зарегистрировано {number}/{len(missing)}")
            save_state(path, state)
        if pause:
            time.sleep(pause)


def fetch_agent_config(api: Api, state: dict[str, Any]) -> dict[str, Any]:
    """Thresholds, slots and timezone from the server — the agent hard-codes none (ADR-004).

    A few computers are asked, not all of them: one token may have been revoked, but a server
    that answers none of them is not configured and there is nothing to measure against.
    """
    for record in list(state["devices"].values())[:CONFIG_ATTEMPTS]:
        response = api.call("GET", "/api/agent/config", headers=device_headers(record["token"]))
        if response.status == 200:
            return response.payload
        warn(f"конфигурация агента: {response.status} {response.detail}")
    raise SimulatorError("ни одно устройство не получило конфигурацию: проверьте сервер")


def send_history(
    api: Api,
    devices: Sequence[SimDevice],
    state: dict[str, Any],
    days: Sequence[date],
    slots: Sequence[Slot],
    tz: tzinfo,
    thresholds: Thresholds,
    now: datetime,
    workers: int,
    counters: Counters,
) -> None:
    """Send the history of every computer in batches, in parallel over the computers.

    A batch that the server refuses is counted and the run goes on: one bad answer must not
    cost the whole history of a region.
    """
    total = len(devices)

    def one(device: SimDevice) -> None:
        record = state["devices"].get(device.device_uid)
        if record is None:
            counters.add(devices_done=1)
            return
        headers = device_headers(record["token"])
        items = device_measurements(device, days, slots, tz, thresholds, now)
        for batch in chunks(items, MAX_BATCH_SIZE):
            try:
                response = api.call(
                    "POST", "/api/measurements/batch", body={"items": list(batch)}, headers=headers
                )
            except SimulatorError as error:
                warn(f"{device.device_uid}: батч не отправлен ({error})")
                counters.add(failed=len(batch))
                continue
            if response.status != 200:
                warn(f"{device.device_uid}: батч {response.status} {response.detail}")
                counters.add(failed=len(batch))
                continue
            results = response.payload.get("results", [])
            stored = sum(1 for result in results if result["status"] == 201)
            counters.add(stored=stored, duplicates=len(results) - stored)
        for period in device_outages(device, days, slots, tz, now):
            try:
                answer = api.call("POST", "/api/outages", body=period, headers=headers)
            except SimulatorError as error:
                warn(f"{device.device_uid}: простой не отправлен ({error})")
                continue
            if answer.status in (201, 409):
                counters.add(outages=1)
        counters.add(devices_done=1)
        done = counters.devices_done
        if done % 50 == 0 or done == total:
            say(
                f"  замеры {done}/{total} ПК · принято {counters.stored} · "
                f"повторов {counters.duplicates} · ошибок {counters.failed}"
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, devices))


def send_heartbeats(
    api: Api, devices: Sequence[SimDevice], state: dict[str, Any], workers: int, counters: Counters
) -> None:
    """Tell the server the computers are alive — last, so the signal is as fresh as it gets.

    It is one signal, not a living agent, and that is the short leash of the demo data. Only the
    handler of the heartbeat moves ``last_seen_at`` (a batch of measurements does not), so
    ``offline_after_s`` later — 15 minutes by default — every school reads «Нет соединения» in
    working hours and «Нет данных» outside them, whatever it measured; with ``make worker``
    running, ``incidents.detect_all`` then opens an incident «Нет соединения» on every line.
    Before a demo the simulator is run again: registrations and measurements are skipped as
    duplicates, and the heartbeats start the window anew (README, «Ограничения»).
    """

    def one(device: SimDevice) -> None:
        record = state["devices"].get(device.device_uid)
        if record is None:
            return
        body = {"sent_at": datetime.now(UTC).isoformat(), "agent_version": AGENT_VERSION}
        try:
            response = api.call(
                "POST",
                "/api/devices/heartbeat",
                body=body,
                headers=device_headers(record["token"]),
            )
        except SimulatorError as error:
            warn(f"{device.device_uid}: heartbeat не отправлен ({error})")
            return
        if response.status == 204:
            counters.add(heartbeats=1)
        else:
            warn(f"{device.device_uid}: heartbeat {response.status} {response.detail}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, devices))


# --- Plan and report --------------------------------------------------------------------------


def profile_counts(schools: Iterable[SimSchool]) -> dict[str, int]:
    counts = dict.fromkeys(PROFILE_TITLES, 0)
    for school in schools:
        counts[school.profile] += 1
    return counts


def plan_lines(
    args: argparse.Namespace,
    days: Sequence[date],
    slots: Sequence[Slot],
    tz: tzinfo,
    now: datetime,
) -> list[str]:
    """Plan of the run: what will be generated and how much of it (``--dry-run`` prints it).

    The counts are the ones the run will really send: the slots of today that have not come yet
    are not measured, so they are not promised either.
    """
    schools = assign_profiles(
        [
            SimSchool(
                school_id=index + 1,
                school_code=f"VKO-SIM-{index + 1:03d}",
                full_name=f"Школа {index + 1}",
                index=index,
                contract_down_mbps=100.0,
                contract_up_mbps=100.0,
            )
            for index in range(args.schools)
        ],
        FALLBACK_THRESHOLDS,
    )
    devices = build_devices(schools, args.devices)
    counts = profile_counts(schools)
    per_device = [
        sum(
            1
            for day in days
            for moment in slot_moments(device.device_uid, day, slots, tz)
            if moment <= now
        )
        for device in devices
    ]
    measurements = sum(per_device)
    batches = sum(math.ceil(number / MAX_BATCH_SIZE) for number in per_device)
    outages = sum(len(device_outages(device, days, slots, tz, now)) for device in devices)
    lines = [
        "План симуляции:",
        f"  школ:       {args.schools}",
        f"  устройств:  {args.devices}",
        f"  дней:       {args.days}"
        + (
            f" (сервер примет {len(days)}: очередь агента — 31 сут.)"
            if args.days > len(days)
            else ""
        ),
        f"  слотов:     {len(slots)} в день",
        f"  замеров:    {measurements} (батчей по {MAX_BATCH_SIZE}: {batches})",
        f"  простоев:   {outages}",
        f"  Wi-Fi ПК:   {sum(1 for device in devices if device.wifi)}",
        "  профили школ: "
        + ", ".join(f"{PROFILE_TITLES[name]} — {count}" for name, count in counts.items()),
    ]
    return lines


def sample_lines(days: Sequence[date], slots: Sequence[Slot], tz: tzinfo) -> list[str]:
    """One measurement of every profile with the fallback thresholds: the check of the generator.

    The status the profile aims at is printed next to the one the rule of ADR-004 gives the
    generated numbers; they must be equal, and the test of the simulator asserts exactly that.
    """
    day = days[-1] if days else datetime.now(UTC).date()
    lines = ["Пример замера по профилям (пороги по умолчанию, проверка генератора):"]
    for profile in PROFILE_TITLES:
        device = SimDevice(
            device_uid=f"sim-VKO-SIM-001-{profile}",
            hostname="PC-SIM",
            school_id=1,
            school_code="VKO-SIM-001",
            profile=profile,
            contract_down_mbps=100.0,
            contract_up_mbps=100.0,
        )
        moment = slot_moments(device.device_uid, day, slots, tz)[min(2, len(slots) - 1)]
        item = measurement(device, moment, FALLBACK_THRESHOLDS)
        got = expected_quality(item, FALLBACK_THRESHOLDS)
        numbers = (
            "нет связи"
            if item["connection_status"] == "offline"
            else (
                f"{item['download_mbps']}/{item['upload_mbps']} Мбит/с · "
                f"ping {item['ping_ms']} мс · jitter {item['jitter_ms']} мс · "
                f"потери {item['packet_loss_pct']} %"
            )
        )
        mark = "ок" if got == target_quality(profile, moment) else "РАСХОЖДЕНИЕ"
        lines.append(f"  {PROFILE_TITLES[profile]:>20}: {numbers} → {got} ({mark})")
    return lines


# --- Entry point --------------------------------------------------------------------------------


def positive_int(value: str) -> int:
    """argparse type: a strictly positive integer."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(
            f"ожидается положительное целое число, получено {value}",
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simulate.py",
        description="Симулятор агентов: школы, ПК и история замеров для демо и нагрузки.",
    )
    parser.add_argument(
        "--schools",
        type=positive_int,
        default=DEFAULT_SCHOOLS,
        help=f"сколько школ (по умолчанию {DEFAULT_SCHOOLS})",
    )
    parser.add_argument(
        "--devices",
        type=positive_int,
        default=DEFAULT_DEVICES,
        help=f"сколько ПК (по умолчанию {DEFAULT_DEVICES})",
    )
    parser.add_argument(
        "--days",
        type=positive_int,
        default=DEFAULT_DAYS,
        help=f"глубина истории в днях (по умолчанию {DEFAULT_DAYS};"
        f" сервер принимает не больше {HISTORY_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--api",
        default=os.environ.get("API_BASE_URL", DEFAULT_API),
        help=f"адрес сервера (по умолчанию {DEFAULT_API} или API_BASE_URL)",
    )
    parser.add_argument(
        "--admin-email",
        default=os.environ.get("SIM_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL),
        help=f"администратор для кодов установки (по умолчанию {DEFAULT_ADMIN_EMAIL})",
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("SIM_ADMIN_PASSWORD"),
        help="пароль администратора; по умолчанию — переменная SIM_ADMIN_PASSWORD",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=default_state_path(),
        help="файл с токенами зарегистрированных ПК (вне git)",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=DEFAULT_WORKERS,
        help=f"сколько ПК отправляют замеры параллельно (по умолчанию {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--register-rate",
        type=positive_int,
        default=DEFAULT_REGISTER_RATE,
        help="регистраций в минуту; должно совпадать с AGENT_REGISTER_RATE_LIMIT сервера",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только план и примеры замеров, без обращений к серверу",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    """Fill the installation: schools → computers → configuration → history → heartbeats."""
    now = datetime.now(UTC)
    api = Api(args.api)
    state = load_state(args.state)
    known_api = state.get("api")
    if known_api and known_api != args.api:
        # The tokens of the file belong to another installation: without this the run dies much
        # later, on the configuration of the agent, with a message about nothing.
        raise SimulatorError(
            f"состояние {args.state} — от сервера {known_api}, а запуск против {args.api}: "
            "токены другого сервера не подойдут; возьмите другой --state или удалите файл"
        )
    state["api"] = args.api

    admin = AdminSession(api, args.admin_email, args.admin_password)
    admin.login()
    schools = fetch_schools(admin, args.schools)
    say(f"Школ найдено: {len(schools)} (нужно {args.schools})")
    schools = fetch_contracts(admin, schools, state, args.workers)
    schools = fetch_rooms(admin, schools, state, args.workers)

    devices = build_devices(schools, args.devices)
    register_devices(api, admin, devices, state, args.state, args.register_rate)
    save_state(args.state, state)
    registered = sum(1 for device in devices if device.device_uid in state["devices"])
    if not registered:
        raise SimulatorError("ни один ПК не зарегистрирован: смотрите сообщения выше")

    config = fetch_agent_config(api, state)
    thresholds = Thresholds.from_config(config)
    slots = [
        Slot(clock.fromisoformat(slot["start"]), clock.fromisoformat(slot["end"]))
        for slot in config["schedule_slots"]
    ]
    tz = zone(config["timezone"])
    # The depth does not depend on the timezone, so it is warned about in ``main`` — before the
    # registration, not after it.
    days = history_days(args.days, now, tz)

    # The profiles need the thresholds of the server, so the schools get them after the config.
    schools = assign_profiles(schools, thresholds)
    devices = build_devices(schools, args.devices)
    say(
        "Профили школ: "
        + ", ".join(
            f"{PROFILE_TITLES[name]} — {count}"
            for name, count in profile_counts(schools).items()
            if count
        )
    )

    counters = Counters()
    say(f"Замеры: {len(days)} сут. × {len(slots)} слотов × {len(devices)} ПК")
    send_history(api, devices, state, days, slots, tz, thresholds, now, args.workers, counters)
    send_heartbeats(api, devices, state, args.workers, counters)
    save_state(args.state, state)

    say(
        f"Готово: принято {counters.stored}, повторов {counters.duplicates}, "
        f"ошибок {counters.failed}, простоев {counters.outages}, "
        f"heartbeat {counters.heartbeats}; состояние — {args.state}"
    )
    say(
        "Статусы школ держатся, пока агенты считаются живыми: через offline_after_s "
        "(по умолчанию 15 мин) все школы станут «Нет соединения». Перед демо запустите "
        "симулятор ещё раз — повторный прогон быстрый."
    )
    return 0 if counters.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(UTC)
    tz = zone(FALLBACK_TIMEZONE)
    days = history_days(args.days, now, tz)
    # Said before anything is sent: a run over a thousand computers takes hours, and the depth
    # of the history must not come as a surprise at the end of it.
    if args.days > len(days):
        warn(history_warning(args.days, len(days)))
    if args.dry_run:
        say("\n".join(plan_lines(args, days, FALLBACK_SLOTS, tz, now)))
        say("\n".join(sample_lines(days, FALLBACK_SLOTS, tz)))
        return 0
    if not args.admin_password:
        warn(
            "Нужен пароль администратора: --admin-password или переменная SIM_ADMIN_PASSWORD "
            "(локальные dev-пользователи — AGENTS.md §7)"
        )
        return 2
    try:
        return run(args)
    except SimulatorError as error:
        warn(f"Симулятор остановлен: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
