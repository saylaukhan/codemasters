"""Incident detection with hysteresis (T-40; ТЗ п. 18, п. 19; plan.md §7; ADR-007).

Every active rule is applied to every line that is not disabled, of a school that is not
deactivated, after each measurement of the line and every 5 minutes by beat. The evidence is
the rated measurements of the line — not Wi‑Fi, judged on receipt (T-18) — read against the
thresholds of their own snapshot, so a later change of a profile never reopens the past
(ADR-004). A metric the agent did not measure says
nothing, neither a violation nor a norm. «Нет соединения» is an offline measurement or, in the
working hours of the school, the silence of every device of the line for longer than
``offline_after_s`` (ADR-014).

A run is the violations in a row up to the newest result. It opens an incident when it has N
violations or lasts T minutes from its first violation to its last; a single deviation lasts
nothing, so it never opens one. The incident starts at the first violation of the run. While it
is open for the detection, a new violation only moves ``last_violation_at``; M normal results
in a row after the last violation set ``restored_at`` to the first of them. Status is changed
by people only (T-41): the detection never moves it. A run never reaches back past the moment an
earlier incident of the same line and rule was restored.

Readings taken inside a quiet interval of the calendar — the vacations and the holidays of the
school, a planned-works window of the provider of the line — are dropped before any of this, so
such a reading opens no incident and extends no open one (T-70, docs/design/README.md §6.5).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, select, text
from sqlalchemy import Sequence as DbSequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    Heartbeat,
    Incident,
    IncidentEvent,
    IncidentRule,
    Line,
    Measurement,
    MonitoringPoint,
    School,
    SystemSettings,
)
from app.models.incident import OPEN_FOR_DETECTION
from app.services.calendar import covers, line_windows, quiet_periods
from app.services.settings import system_settings
from app.services.status import WIFI
from app.services.working_hours import is_working_time, school_hours, working_windows

NO_CONNECTION = "no_connection"
OFFLINE = "offline"

# Rated measurements of a line read per run: at 5 a day that is 20 days, far longer than any
# run of N violations or M normal results.
HISTORY_LIMIT = 100

# First key of the advisory lock that makes the detection of one line sequential: the task
# after a measurement and the beat run may meet on the same line (T-40).
LOCK_KEY = 40

INCIDENT_NUMBERS = DbSequence("incident_number_seq")


@dataclass(frozen=True)
class Reading:
    """One rated measurement of the line as the detection sees it."""

    measured_at: datetime
    offline: bool
    values: dict[str, float | None]
    # Metric → (value, limit) of the breaches in its thresholds snapshot.
    breaches: dict[str, tuple[float, float]]

    def verdict(self, metric: str) -> bool | None:
        """True — a violation of ``metric``, False — a norm, None — says nothing about it."""
        if metric == NO_CONNECTION:
            return self.offline
        if self.values[metric] is None:
            return None
        return metric in self.breaches


@dataclass(frozen=True)
class Run:
    """Violations in a row up to now; ``count`` has only measurements, not silence."""

    first_at: datetime
    last_at: datetime
    count: int
    value: float | None = None
    threshold: float | None = None


@dataclass
class Detection:
    """Incidents one run opened, moved on and restored — what the notifications of T-42 read."""

    opened: list[int] = field(default_factory=list)
    updated: list[int] = field(default_factory=list)
    restored: list[int] = field(default_factory=list)

    def extend(self, other: "Detection") -> None:
        self.opened += other.opened
        self.updated += other.updated
        self.restored += other.restored


def reading(row: Any) -> Reading | None:
    """Measurement row as a reading; None for one without a verdict of the server."""
    snapshot = row.thresholds_snapshot
    if not isinstance(snapshot, dict) or snapshot.get("rates_line") is False:
        return None
    return Reading(
        measured_at=row.measured_at,
        offline=row.connection_status == OFFLINE,
        values={
            "download_mbps": row.download_mbps,
            "upload_mbps": row.upload_mbps,
            "ping_ms": row.ping_ms,
            "jitter_ms": row.jitter_ms,
            "packet_loss_pct": row.packet_loss_pct,
        },
        breaches={
            breach["metric"]: (breach["value"], breach["limit"])
            for breach in snapshot.get("breaches", [])
        },
    )


def judged(
    readings: Sequence[Reading], metric: str, since: datetime | None
) -> list[tuple[Reading, bool]]:
    """Readings that say something about ``metric`` after ``since``, newest first."""
    found = []
    for item in readings:
        if since is not None and item.measured_at <= since:
            break
        verdict = item.verdict(metric)
        if verdict is not None:
            found.append((item, verdict))
    return found


def current_run(results: Sequence[tuple[Reading, bool]], metric: str) -> Run | None:
    """Violations in a row from the newest result back; None when the newest is a norm."""
    run = [item for item, _ in _head(results, violated=True)]
    if not run:
        return None
    newest = run[0]
    value, threshold = newest.breaches.get(metric, (None, None))
    return Run(
        first_at=run[-1].measured_at,
        last_at=newest.measured_at,
        count=len(run),
        value=value,
        threshold=threshold,
    )


def normal_streak(results: Sequence[tuple[Reading, bool]], after: datetime) -> list[Reading]:
    """Norms in a row from the newest result back that came after ``after``, newest first."""
    return [item for item, _ in _head(results, violated=False) if item.measured_at > after]


def _head(results: Sequence[tuple[Reading, bool]], *, violated: bool) -> list[tuple[Reading, bool]]:
    head = []
    for result in results:
        if result[1] is not violated:
            break
        head.append(result)
    return head


def opens(rule: IncidentRule, run: Run) -> bool:
    """N violations in a row or T minutes from the first violation of the run to its last."""
    if rule.consecutive_violations is not None and run.count >= rule.consecutive_violations:
        return True
    return rule.duration_min is not None and run.last_at - run.first_at >= timedelta(
        minutes=rule.duration_min
    )


async def incident_number(session: AsyncSession, settings: SystemSettings, now: datetime) -> str:
    """``INC-<year>-<six digits>``: the year of ``now`` in the zone of the system, the digits
    from one sequence for rule and manual incidents (ADR-007)."""
    serial = await session.scalar(select(INCIDENT_NUMBERS.next_value()))
    year = now.astimezone(ZoneInfo(settings.timezone)).year
    return f"INC-{year}-{serial:06d}"


async def line_readings(session: AsyncSession, line_id: int, now: datetime) -> list[Reading]:
    """The last rated measurements of the line up to ``now``, newest first."""
    rows = await session.execute(
        select(
            Measurement.measured_at,
            Measurement.connection_status,
            Measurement.download_mbps,
            Measurement.upload_mbps,
            Measurement.ping_ms,
            Measurement.jitter_ms,
            Measurement.packet_loss_pct,
            Measurement.thresholds_snapshot,
        )
        .where(
            Measurement.line_id == line_id,
            Measurement.measured_at <= now,
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.quality_status.is_not(None),
        )
        .order_by(Measurement.measured_at.desc())
        .limit(HISTORY_LIMIT)
    )
    return [item for item in map(reading, rows) if item is not None]


async def silent_since(
    session: AsyncSession, line: Line, settings: SystemSettings, now: datetime
) -> datetime | None:
    """Since when the line is silent in the current working window, when that is longer than
    ``offline_after_s``; None while a device is heard, outside working hours, or for a line no
    device has ever been heard on (nothing to lose).

    Silence counts from the opening of today's working hours at the earliest: a computer
    switched off for the night is not a broken line (ADR-014).
    """
    heard = (
        select(func.max(Heartbeat.ts))
        .where(Heartbeat.device_id == Device.id, Heartbeat.ts <= now)
        .scalar_subquery()
    )
    seen = func.coalesce(case((Device.last_seen_at <= now, Device.last_seen_at)), heard)
    last_seen = await session.scalar(
        select(func.max(seen))
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(MonitoringPoint.line_id == line.id, Device.status == "active")
    )
    if last_seen is None:
        return None
    hours = (await school_hours(session, [line.school_id], settings))[line.school_id]
    if not is_working_time(hours, settings.timezone, now):
        return None
    windows = working_windows(hours, settings.timezone, last_seen, now)
    if not windows:
        return None
    since = windows[-1][0]
    if now - since <= timedelta(seconds=settings.offline_after_s):
        return None
    return since


def watched_lines() -> Select[tuple[int]]:
    """Lines the detection watches: not disabled, of a school that is not deactivated."""
    return (
        select(Line.id)
        .join(School, School.id == Line.school_id)
        .where(Line.status != "disabled", School.is_active)
    )


async def detection_line_ids(session: AsyncSession) -> list[int]:
    return list(await session.scalars(watched_lines().order_by(Line.id)))


async def detect_line(session: AsyncSession, line_id: int, *, now: datetime) -> Detection:
    """Apply every active rule to the line at ``now``; the caller commits.

    Runs as the owner of the tables, outside any scope (ADR-008): the detection sees every line.
    """
    detection = Detection()
    await session.execute(select(func.pg_advisory_xact_lock(LOCK_KEY, line_id)))
    if await session.scalar(watched_lines().where(Line.id == line_id)) is None:
        return detection
    line = await session.get_one(Line, line_id)
    rules = (
        await session.scalars(
            select(IncidentRule).where(IncidentRule.is_active).order_by(IncidentRule.id)
        )
    ).all()
    if not rules:
        return detection

    settings = await system_settings(session)
    readings = await line_readings(session, line_id, now)
    # The calendar over the history that was read: a vacation of the school, a holiday of the
    # oblast, a works window of this provider (T-70).
    quiet = line_windows(
        (
            await quiet_periods(
                session,
                [line.school_id],
                start=readings[-1].measured_at if readings else now,
                end=now,
            )
        )[line.school_id],
        line.provider_id,
    )
    readings = [item for item in readings if not covers(quiet, item.measured_at)]
    silence = (
        await silent_since(session, line, settings, now)
        if any(rule.metric == NO_CONNECTION for rule in rules) and not covers(quiet, now)
        else None
    )
    open_incidents = {
        incident.rule_id: incident
        for incident in await session.scalars(
            select(Incident).where(Incident.line_id == line_id, text(OPEN_FOR_DETECTION))
        )
    }
    restored_until: dict[int, datetime] = {
        rule_id: moment
        for rule_id, moment in await session.execute(
            select(Incident.rule_id, func.max(Incident.restored_at))
            .where(Incident.line_id == line_id, Incident.restored_at.is_not(None))
            .group_by(Incident.rule_id)
        )
        if rule_id is not None
    }

    for rule in rules:
        since = restored_until.get(rule.id)
        results = judged(readings, rule.metric, since)
        run = current_run(results, rule.metric)
        if rule.metric == NO_CONNECTION and silence is not None:
            quiet_from = silence if since is None else max(silence, since)
            run = Run(
                first_at=quiet_from if run is None else min(run.first_at, quiet_from),
                last_at=now,
                count=0 if run is None else run.count,
            )

        incident = open_incidents.get(rule.id)
        if incident is not None:
            if run is not None:
                if incident.last_violation_at is None or run.last_at > incident.last_violation_at:
                    incident.last_violation_at = run.last_at
                    detection.updated.append(incident.id)
                continue
            streak = normal_streak(results, incident.last_violation_at or incident.started_at)
            if len(streak) >= rule.recovery_normal_count:
                incident.restored_at = streak[-1].measured_at
                session.add(IncidentEvent(incident_id=incident.id, kind="restored", created_at=now))
                detection.restored.append(incident.id)
            continue

        if run is not None and opens(rule, run):
            incident = Incident(
                number=await incident_number(session, settings, now),
                status="new",
                rule_id=rule.id,
                line_id=line.id,
                school_id=line.school_id,
                provider_id=line.provider_id,
                basis_metrics=[
                    {"metric": rule.metric, "value": run.value, "threshold": run.threshold}
                ],
                started_at=run.first_at,
                last_violation_at=run.last_at,
            )
            session.add(incident)
            await session.flush()
            session.add(
                IncidentEvent(
                    incident_id=incident.id, kind="created", to_status="new", created_at=now
                )
            )
            detection.opened.append(incident.id)

    await session.flush()
    return detection
