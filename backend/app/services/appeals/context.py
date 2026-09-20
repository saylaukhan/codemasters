"""Facts an appeal is built from (T-47, ТЗ п. 17, plan.md §8) — and not one personal datum.

The target of a draft is an incident or a line of a school. Both are read in the session of the
request, so RLS answers for the visibility: an incident or a school outside the user's scope
simply does not exist here and the request is a 422 on its field, not a 403 (ADR-008). A line
of another school is the same 422 — the school of an appeal is derived from the line and never
trusted from the request (ADR-005).

The numbers are the raw measurements of the line over the period without Wi-Fi, which measures
the air and not the provider (ADR-012). The thresholds are those the last measurement of the
period was judged by, so the letter argues by what the record itself keeps (ADR-004). The
downtime is the ``outages`` of the line merged and cut to the period; the gaps of the heartbeat
that ``app/services/availability.py`` counts for a school inside its working hours are not in
it yet (docs/known-limitations.md, T-47).

Contacts of ``school_contacts`` are not collected here at all: they are put into the ready text
after the generation (``draft.py``, ADR-011).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Incident, Line, Measurement, Outage, Provider, School
from app.schemas.analytics import MetricStats
from app.schemas.appeals import AppealContext, AppealDraftRequest
from app.schemas.thresholds import ThresholdValues
from app.services.references import invalid_field
from app.services.settings import NOT_CONFIGURED, NOT_CONFIGURED_DETAIL, system_settings
from app.services.status import WIFI
from app.services.thresholds import threshold_profile
from app.services.working_hours import Interval, duration_s, merge

# Metrics of the appeal, in the order of ТЗ п. 17.
METRICS = ("download_mbps", "upload_mbps", "ping_ms", "jitter_ms", "packet_loss_pct")

# A problem measurement is one of these, as the analytics counts them (ADR-004).
PROBLEM_STATUSES = ("unstable", "critical", "offline")

# Measurements quoted to the model (plan.md §8): the problem ones first, the newest on top.
EXCERPT_SIZE = 10


@dataclass(frozen=True)
class MeasurementExcerpt:
    """One measurement of the excerpt: when, what was measured and how it was judged."""

    measured_at: datetime
    download_mbps: float | None
    upload_mbps: float | None
    ping_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float | None
    quality_status: str | None


@dataclass(frozen=True)
class AppealFacts:
    """Everything the draft is made of; the prompt sees ``context`` and ``excerpt`` only."""

    context: AppealContext
    excerpt: list[MeasurementExcerpt]
    # ``appeals_email`` of the provider: the address the letter of T-48 will go to.
    recipient_email: str | None
    timezone: str


def metric_columns() -> list[Any]:
    """Average, minimum and maximum of every metric, labelled for ``metric_stats``."""
    columns: list[Any] = []
    for metric in METRICS:
        column = getattr(Measurement, metric)
        columns += [
            func.avg(column).label(f"avg_{metric}"),
            func.min(column).label(f"min_{metric}"),
            func.max(column).label(f"max_{metric}"),
        ]
    return columns


def metric_stats(row: Any, metric: str) -> MetricStats | None:
    """Stats of one metric; empty when no measurement of the period has a value for it."""
    avg = getattr(row, f"avg_{metric}")
    if avg is None:
        return None
    return MetricStats(
        avg=float(avg),
        min=float(getattr(row, f"min_{metric}")),
        max=float(getattr(row, f"max_{metric}")),
    )


async def appeal_target(
    session: AsyncSession, body: AppealDraftRequest
) -> tuple[str, int, str | None]:
    """Field of the request that names the target, the line of the appeal and, for an incident,
    its number. Unknown ids and a line of another school are a 422 on that field."""
    if body.incident_id is not None:
        incident = await session.scalar(select(Incident).where(Incident.id == body.incident_id))
        if incident is None:
            raise invalid_field("incident_id", "Инцидент не найден")
        return "incident_id", incident.line_id, incident.number
    # The validator of ``AppealDraftRequest`` guarantees the pair; ``cast`` says so to mypy.
    school_id, line_id = cast(int, body.school_id), cast(int, body.line_id)
    if await session.scalar(select(School.id).where(School.id == school_id)) is None:
        raise invalid_field("school_id", "Школа не найдена")
    line_school_id = await session.scalar(select(Line.school_id).where(Line.id == line_id))
    if line_school_id is None:
        raise invalid_field("line_id", "Линия не найдена")
    if line_school_id != school_id:
        raise invalid_field("line_id", "Линия принадлежит другой школе")
    return "line_id", line_id, None


async def period_thresholds(
    session: AsyncSession, measured: tuple[Any, ...], *, line_id: int, region_id: int
) -> ThresholdValues:
    """Thresholds of the letter: the snapshot of the last measurement of the period, else the
    profile in force for the line (ADR-004). No profile at all is an incomplete installation."""
    snapshot = await session.scalar(
        select(Measurement.thresholds_snapshot)
        .where(*measured, Measurement.thresholds_snapshot.is_not(None))
        .order_by(Measurement.measured_at.desc())
        .limit(1)
    )
    if snapshot is not None:
        return ThresholdValues.model_validate(snapshot)
    profile = await threshold_profile(session, line_id=line_id, region_id=region_id)
    if profile is None:
        raise ApiError(503, NOT_CONFIGURED, NOT_CONFIGURED_DETAIL)
    return ThresholdValues.model_validate(profile, from_attributes=True)


async def line_outages(
    session: AsyncSession, line_id: int, *, start: datetime, end: datetime
) -> tuple[int, int]:
    """Number of episodes without connection on the line and their whole seconds (ADR-014).

    Reports of several computers of one line overlap: they are merged into episodes and cut to
    the period, as the report of a school does it (``app/services/exports/report.py``).
    """
    intervals: list[Interval] = [
        (max(started_at, start), end if ended_at is None else min(ended_at, end))
        for started_at, ended_at in await session.execute(
            select(Outage.started_at, Outage.ended_at).where(
                Outage.line_id == line_id,
                Outage.started_at < end,
                or_(Outage.ended_at.is_(None), Outage.ended_at > start),
            )
        )
    ]
    merged = merge(intervals)
    return len(merged), int(duration_s(merged))


async def appeal_excerpt(
    session: AsyncSession, measured: tuple[Any, ...]
) -> list[MeasurementExcerpt]:
    """Measurements quoted to the model: the problem ones first, then the rest, newest on top."""
    rows = await session.execute(
        select(
            Measurement.measured_at,
            *(getattr(Measurement, m) for m in METRICS),
            Measurement.quality_status,
        )
        .where(*measured)
        .order_by(
            case((Measurement.quality_status.in_(PROBLEM_STATUSES), 0), else_=1),
            Measurement.measured_at.desc(),
        )
        .limit(EXCERPT_SIZE)
    )
    return [MeasurementExcerpt(*row) for row in rows]


async def appeal_facts(
    session: AsyncSession, body: AppealDraftRequest, *, now: datetime
) -> AppealFacts:
    """Context of the appeal of ``body`` (ТЗ п. 17) with the excerpt of its measurements."""
    field, line_id, incident_number = await appeal_target(session, body)
    row = (
        await session.execute(
            select(
                Line,
                School.school_code,
                School.full_name.label("school_name"),
                School.region_id,
                Provider.name.label("provider_name"),
                Provider.appeals_email,
            )
            .join(School, School.id == Line.school_id)
            .join(Provider, Provider.id == Line.provider_id)
            .where(Line.id == line_id)
        )
    ).one_or_none()
    if row is None:
        raise invalid_field(field, "Линия обращения не найдена")
    line: Line = row.Line

    measured = (
        Measurement.line_id == line_id,
        Measurement.measured_at >= body.period_from,
        Measurement.measured_at < body.period_to,
        Measurement.iface_type.is_distinct_from(WIFI),
    )
    totals = (
        await session.execute(
            select(
                func.count().label("measurements_count"),
                func.count()
                .filter(Measurement.quality_status.in_(PROBLEM_STATUSES))
                .label("problem_count"),
                *metric_columns(),
            ).where(*measured)
        )
    ).one()
    # What has not happened yet is not downtime, as in the report of a school (T-32).
    end = max(min(body.period_to, now), body.period_from)
    outages_count, outages_duration_s = await line_outages(
        session, line_id, start=body.period_from, end=end
    )
    context = AppealContext(
        incident_id=body.incident_id,
        incident_number=incident_number,
        school_id=line.school_id,
        school_code=row.school_code,
        school_name=row.school_name,
        line_id=line.id,
        line_identifier=line.line_identifier,
        provider_id=line.provider_id,
        provider_name=row.provider_name,
        contract_number=line.contract_number,
        contract_date=line.contract_date,
        contract_down_mbps=line.contract_down_mbps,
        contract_up_mbps=line.contract_up_mbps,
        period_from=body.period_from,
        period_to=body.period_to,
        measurements_count=totals.measurements_count,
        problem_count=totals.problem_count,
        download_mbps=metric_stats(totals, "download_mbps"),
        upload_mbps=metric_stats(totals, "upload_mbps"),
        ping_ms=metric_stats(totals, "ping_ms"),
        jitter_ms=metric_stats(totals, "jitter_ms"),
        packet_loss_pct=metric_stats(totals, "packet_loss_pct"),
        thresholds=await period_thresholds(
            session, measured, line_id=line_id, region_id=row.region_id
        ),
        outages_count=outages_count,
        outages_duration_s=outages_duration_s,
    )
    return AppealFacts(
        context=context,
        excerpt=await appeal_excerpt(session, measured),
        recipient_email=row.appeals_email,
        timezone=(await system_settings(session)).timezone,
    )
