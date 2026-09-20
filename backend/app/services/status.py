"""Status of a measurement on receipt (T-18) and of a school on the map (T-16); ADR-004.

Two steps of the same rule of ТЗ п. 13. The first judges one measurement against the thresholds
of its line and keeps the numbers it judged by inside the record, so a later change of the
profile never rewrites history and a dispute with a provider is settled by the record alone
(ТЗ п. 11, plan.md §6). The second folds the last measurements of the main line into the status
of a school, where a silent agent overrides them: no heartbeat for longer than
``offline_after_s`` in working hours means «Нет соединения», outside them «Нет данных» — a
computer switched off for the night is not a broken line (ADR-014). The third, run
periodically, folds the ``contract_ok`` of the main line over a window into the sustained
mismatch of ТЗ п. 14 (T-29).
"""

from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, case, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import (
    Device,
    Heartbeat,
    Line,
    Measurement,
    MonitoringPoint,
    School,
    ThresholdProfile,
)
from app.schemas.agent import MeasurementCreate
from app.schemas.statuses import ProfileScope, QualityStatus, SchoolStatus
from app.schemas.thresholds import MetricBreach, ThresholdsSnapshot
from app.services.settings import NOT_CONFIGURED, NOT_CONFIGURED_DETAIL, system_settings
from app.services.thresholds import threshold_profile
from app.services.working_hours import is_working_time, school_hours

# Statuses of a measurement from the mildest to the worst (ADR-004).
SEVERITY: tuple[SchoolStatus, ...] = ("normal", "unstable", "critical", "offline")

# Wi-Fi does not rate the line: the air, not the provider, is measured through it (ADR-012).
WIFI = "wifi"

# Whether the metric must stay above its limit (speeds) or below it (ping, jitter, loss).
AT_LEAST = True
AT_MOST = False


@dataclass(frozen=True)
class LineRules:
    """What one line is judged by: its threshold profile and the speeds of its contract."""

    profile: ThresholdProfile
    contract_down_mbps: float | None
    contract_up_mbps: float | None


@dataclass(frozen=True)
class Evaluation:
    """Verdict of the server on one measurement; its three fields go into ``measurements``."""

    quality_status: QualityStatus
    thresholds_snapshot: dict[str, Any]
    contract_ok: bool | None


async def line_rules(session: AsyncSession, line_id: int) -> LineRules:
    """Thresholds of the line and the speeds its contract promises (ТЗ п. 11, п. 14).

    The profile is the most specific active one — the line's, its district's or the global one
    (ADR-004). A database without the global profile is an incomplete installation, so it
    answers 503 and the agent resends the measurement later instead of losing it (ADR-006).
    """
    line = (
        await session.execute(
            select(Line.contract_down_mbps, Line.contract_up_mbps, School.region_id)
            .join(School, School.id == Line.school_id)
            .where(Line.id == line_id)
        )
    ).one()
    profile = await threshold_profile(session, line_id=line_id, region_id=line.region_id)
    if profile is None:
        raise ApiError(503, NOT_CONFIGURED, NOT_CONFIGURED_DETAIL)
    return LineRules(
        profile=profile,
        contract_down_mbps=line.contract_down_mbps,
        contract_up_mbps=line.contract_up_mbps,
    )


def breaches(item: MeasurementCreate, profile: ThresholdProfile) -> list[MetricBreach]:
    """Metrics of the measurement past their limits, with how far past they are (plan.md §6).

    A metric the agent did not measure is not a breach: an empty value is «нет данных», not a
    fault of the line.
    """
    limits = (
        ("download_mbps", item.download_mbps, profile.download_min_mbps, AT_LEAST),
        ("upload_mbps", item.upload_mbps, profile.upload_min_mbps, AT_LEAST),
        ("ping_ms", item.ping_ms, profile.ping_max_ms, AT_MOST),
        ("jitter_ms", item.jitter_ms, profile.jitter_max_ms, AT_MOST),
        ("packet_loss_pct", item.packet_loss_pct, profile.packet_loss_max_pct, AT_MOST),
    )
    found = []
    for metric, value, limit, at_least in limits:
        if value is None:
            continue
        past = limit - value if at_least else value - limit
        if past <= 0:
            continue
        found.append(
            MetricBreach(
                metric=metric,
                value=value,
                limit=limit,
                # A limit of zero has no percent: any breach of it counts as a gross one.
                deviation_pct=100 * past / limit if limit else None,
            )
        )
    return found


def quality(
    item: MeasurementCreate, found: Sequence[MetricBreach], allowed_pct: float
) -> QualityStatus:
    """Status of the measurement itself (ТЗ п. 13, plan.md §6).

    No connection at all beats any number. Otherwise: everything inside the thresholds →
    «Норма»; exactly one metric past its limit by no more than ``allowed_pct`` → «Нестабильно»;
    several metrics or a deviation larger than that → «Критично».
    """
    if item.connection_status == "offline":
        return "offline"
    if not found:
        return "normal"
    gross = [
        breach
        for breach in found
        if breach.deviation_pct is None or breach.deviation_pct > allowed_pct
    ]
    return "unstable" if len(found) == 1 and not gross else "critical"


def contract_kept(item: MeasurementCreate, rules: LineRules, *, rates_line: bool) -> bool | None:
    """Whether the fact reaches the speeds the contract promises (ТЗ п. 14, ADR-004).

    The flag is separate from the quality status: a line can be slower than the contract and
    still pass the thresholds, and the other way round. Empty while there is nothing to
    compare — no contract speeds on the line, nothing measured, or Wi-Fi, which says nothing
    about the line.
    """
    if not rates_line:
        return None
    promised = [
        (item.download_mbps, rules.contract_down_mbps),
        (item.upload_mbps, rules.contract_up_mbps),
    ]
    compared = [(fact, limit) for fact, limit in promised if fact is not None and limit is not None]
    if not compared:
        return None
    return all(fact >= limit for fact, limit in compared)


def evaluate(item: MeasurementCreate, rules: LineRules) -> Evaluation:
    """Judge one measurement at the moment it is received (ТЗ п. 11, ADR-004).

    A Wi-Fi measurement is judged like any other, but marked in the snapshot as one that does
    not rate the line: the school status, the aggregates and the contract skip it (ADR-012).
    """
    profile = rules.profile
    rates_line = item.iface_type != WIFI
    found = breaches(item, profile)
    snapshot = ThresholdsSnapshot(
        profile_id=profile.id,
        profile_scope=cast(ProfileScope, profile.scope),
        download_min_mbps=profile.download_min_mbps,
        upload_min_mbps=profile.upload_min_mbps,
        ping_max_ms=profile.ping_max_ms,
        jitter_max_ms=profile.jitter_max_ms,
        packet_loss_max_pct=profile.packet_loss_max_pct,
        unstable_deviation_pct=profile.unstable_deviation_pct,
        contract_down_mbps=rules.contract_down_mbps,
        contract_up_mbps=rules.contract_up_mbps,
        rates_line=rates_line,
        breaches=found,
    )
    return Evaluation(
        quality_status=quality(item, found, profile.unstable_deviation_pct),
        thresholds_snapshot=snapshot.model_dump(mode="json"),
        contract_ok=contract_kept(item, rules, rates_line=rates_line),
    )


def worst_of_the_majority(statuses: Sequence[str]) -> SchoolStatus:
    """Fold the last measurements into one status: the median of them by severity.

    The rule of this task (ТЗ п. 13, ADR-004: N = 3 by default): a single deviation among the
    last N does not colour the school, two of three do. With fewer measurements than N the
    median of what there is answers, so one measurement speaks for itself.
    """
    ranked = sorted(SEVERITY.index(status) for status in statuses)
    return SEVERITY[ranked[len(ranked) // 2]]


async def school_statuses(
    session: AsyncSession, school_ids: Collection[int], *, now: datetime
) -> dict[int, SchoolStatus]:
    """Status of every school of ``school_ids`` at ``now``, in two queries whatever their number.

    The map and the overview judge hundreds of schools at once (T-22), so the rule of
    ``school_status`` is applied here to all of them together. The last signal of a device is
    ``last_seen_at`` while it is not later than ``now``; a moment in the past is answered by the
    heartbeats, which remember it. Measurements after ``now`` are not known at ``now``.
    """
    if not school_ids:
        return {}
    settings = await system_settings(session)
    hours = await school_hours(session, school_ids, settings)

    heard = (
        select(func.max(Heartbeat.ts))
        .where(Heartbeat.device_id == Device.id, Heartbeat.ts <= now)
        .scalar_subquery()
    )
    seen = func.coalesce(case((Device.last_seen_at <= now, Device.last_seen_at)), heard)
    last_seen: dict[int, datetime | None] = {
        school_id: moment
        for school_id, moment in await session.execute(
            select(MonitoringPoint.school_id, func.max(seen))
            .join(Device, Device.monitoring_point_id == MonitoringPoint.id)
            .where(MonitoringPoint.school_id.in_(school_ids), Device.status == "active")
            .group_by(MonitoringPoint.school_id)
        )
    }

    count = settings.school_status_measurements_count
    # The last measurements of every main line: one index scan per line (line_id, measured_at).
    latest = (
        select(Measurement.measured_at, Measurement.quality_status)
        .where(
            Measurement.line_id == Line.id,
            Measurement.measured_at <= now,
            Measurement.iface_type.is_distinct_from(WIFI),
            Measurement.quality_status.is_not(None),
        )
        .order_by(Measurement.measured_at.desc())
        .limit(count)
        .lateral("latest")
    )
    series: dict[int, list[tuple[datetime, str]]] = defaultdict(list)
    for school_id, measured_at, quality_status in await session.execute(
        select(Line.school_id, latest.c.measured_at, latest.c.quality_status)
        .join(latest, true())
        .where(Line.school_id.in_(school_ids), Line.status == "main")
    ):
        series[school_id].append((measured_at, quality_status))

    statuses: dict[int, SchoolStatus] = {}
    for school_id in school_ids:
        if school_id not in last_seen:
            # Not one active computer of the school is visible: nothing has told us how the
            # line behaves, and silence of a computer that does not exist is not «Нет
            # соединения». A provider of only the reserve line of a school sees it this way
            # too — the computers of the main line are outside his scope (T-44, ADR-008).
            statuses[school_id] = "no_data"
            continue
        moment = last_seen[school_id]
        if moment is None or now - moment > timedelta(seconds=settings.offline_after_s):
            working = is_working_time(hours[school_id], settings.timezone, now)
            statuses[school_id] = "offline" if working else "no_data"
            continue
        # Several main lines of one school: the last ``count`` of all of them together.
        newest = sorted(series[school_id], reverse=True)[:count]
        statuses[school_id] = (
            worst_of_the_majority([status for _, status in newest]) if newest else "no_data"
        )
    return statuses


async def school_status(session: AsyncSession, school_id: int, *, now: datetime) -> SchoolStatus:
    """Status of the school at ``now``: «Нет данных» while nothing has been measured yet.

    Only the main line counts and only measurements that are not made over Wi-Fi: the reserve
    line and the air are not what the school is judged by (ADR-004, ADR-012). Measurements
    received before T-18 carry no status of their own and say nothing here.
    """
    return (await school_statuses(session, [school_id], now=now))[school_id]


async def recompute_contract_compliance(session: AsyncSession, *, now: datetime) -> int:
    """Write the sustained mismatch of every main line at ``now`` onto ``lines`` (ТЗ п. 14).

    The rule of «Решения по умолчанию»: more than ``contract_mismatch_threshold_pct`` of the
    measurements of the main line over the last ``contract_mismatch_window_days`` below the
    contract speed; both come from ``settings`` (T-29). Only measurements with ``contract_ok``
    count: Wi-Fi, a lost connection and a line without contract speeds compare nothing
    (``contract_kept``). A line with nothing to compare, and any line that is not main, is
    cleared to NULL. Returns how many lines got a result; the caller commits.
    """
    settings = await system_settings(session)
    window_days = settings.contract_mismatch_window_days
    compared = func.count(Measurement.contract_ok)
    below = func.count().filter(Measurement.contract_ok.is_(False))
    shares = (
        select(Measurement.line_id, (100.0 * below / compared).label("below_pct"))
        .where(
            Measurement.measured_at > now - timedelta(days=window_days),
            Measurement.measured_at <= now,
            Measurement.contract_ok.is_not(None),
        )
        .group_by(Measurement.line_id)
        .subquery("shares")
    )
    # Recomputed values are not an edit of the line: ``updated_at`` keeps the last edit.
    await session.execute(
        update(Line)
        .where(Line.compliance_checked_at.is_not(None))
        .values(
            compliance_below_pct=None,
            compliance_sustained_mismatch=None,
            compliance_window_days=None,
            compliance_checked_at=None,
            updated_at=Line.updated_at,
        )
    )
    result = await session.execute(
        update(Line)
        .where(Line.id == shares.c.line_id, Line.status == "main")
        .values(
            compliance_below_pct=shares.c.below_pct,
            compliance_sustained_mismatch=shares.c.below_pct
            > settings.contract_mismatch_threshold_pct,
            compliance_window_days=window_days,
            compliance_checked_at=now,
            updated_at=Line.updated_at,
        )
    )
    return cast(CursorResult[Any], result).rowcount
