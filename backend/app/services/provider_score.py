"""Score of a provider over a period (T-68; ТЗ п. 14, п. 19; docs/design/README.md §6.3).

Nothing is counted twice: the measurements, the availability and the share below the contract
come from the analytics of T-27 over the aggregates of T-19, the incidents from the analytics
of T-45, both asked with ``level='provider'``, so the numbers of this screen and of the
analytics screen agree for the same period. The scope and RLS come with them: both reports
stand on ``selected_lines``, where the policies of ADR-008 keep the user inside his own lines,
so a district sees only its own providers and a provider only itself.

Only the reaction time is counted here: how long an incident waited for its first change of
status. The score is 100 minus the penalty of every part, each part weighted by a setting and
each penalty inside 0–1, so the weights of the admin panel are the whole formula (ADR-004).

The planned-works windows of the calendar (T-70) are taken out of the two parts that count the
incidents of the provider itself: an incident that started inside a window the provider
announced, and where it announced it, is neither its reaction time nor its frequency, and the
detection of T-40 opens no new incident there at all. The availability of a school is shared by
every line of it, so an announced window is not subtracted from the availability part of the
score, nor from the act of T-69; widening the exclusion there is a decision of the lead, not of
this module. Every caller reads the period through ``score_window``, the one place the bounds of
the period come from.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import Incident, IncidentEvent, Line, Provider, Region, School, SystemSettings
from app.schemas.analytics import AnalyticsPeriod, AnalyticsRow
from app.schemas.providers import (
    ProviderLineBelowNorm,
    ProviderSchoolRow,
    ProviderScoreDetail,
    ProviderScoreReport,
    ProviderScoreRow,
    ProviderScoreVerdict,
    ProviderScoreWeights,
)
from app.services.analytics import AnalyticsFilters, analytics_report, period_bounds, selected_lines
from app.services.calendar import inside_planned_works, outside_planned_works
from app.services.incident_analytics import incident_analytics_report
from app.services.settings import system_settings
from app.services.status import school_statuses
from app.services.thresholds import active_threshold_profiles, profile_of

PROVIDER_NOT_FOUND = "Поставщик не найден"

# The first change of status of an incident is the answer to it: the rest of the history is the
# work itself (ADR-007), and the score of §6.3 measures how long the answer took.
FIRST_MOVE_KIND = "status_change"


@dataclass(frozen=True)
class ScoreWindow:
    """Period the score is counted over; the incidents of announced works drop out (T-70)."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class Timings:
    """Reaction of the provider to the incidents of the period, in seconds."""

    median_s: int | None = None
    worst_s: int | None = None


def score_window(
    settings: SystemSettings,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    *,
    now: datetime,
) -> ScoreWindow:
    """Bounds of the period, exactly as the analytics of T-27 reads the same query parameters.

    The rows, the card and the act all ask for their period through this function; the
    incidents inside a window of planned works are taken out of the score of that provider
    (``outside_planned_works``), the rest of the period is counted as it happened.
    """
    start, end = period_bounds(period, period_from, period_to, now=now, timezone=settings.timezone)
    return ScoreWindow(start=start, end=end)


def weights_of(settings: SystemSettings) -> ProviderScoreWeights:
    return ProviderScoreWeights(
        below_contract=settings.provider_score_weight_below_contract,
        availability=settings.provider_score_weight_availability,
        reaction=settings.provider_score_weight_reaction,
        incidents=settings.provider_score_weight_incidents,
        pass_pct=settings.provider_score_pass_pct,
        reaction_norm_hours=settings.provider_score_reaction_norm_hours,
    )


def share(value: float) -> float:
    """A penalty is a share of its part: outside 0–1 it would move the score out of 0–100."""
    return max(0.0, min(1.0, value))


def penalties(
    row: AnalyticsRow,
    timings: Timings,
    *,
    incidents_opened: int,
    schools_count: int,
    weights: ProviderScoreWeights,
    availability_min_pct: float,
) -> list[tuple[float, float]]:
    """Every part of the score as (weight, penalty); a part without data does not penalise."""
    below = 0.0 if row.below_contract_pct is None else row.below_contract_pct / 100
    missing_availability = (
        0.0
        if row.availability_pct is None or availability_min_pct <= 0
        else (availability_min_pct - row.availability_pct) / availability_min_pct
    )
    norm_s = weights.reaction_norm_hours * 3600
    late = 0.0 if timings.median_s is None else (timings.median_s - norm_s) / norm_s
    # One incident per school over the period is the whole penalty of that part: the ratio is
    # the number the districts compare providers by, not a threshold of the settings.
    frequency = 0.0 if not schools_count else incidents_opened / schools_count
    return [
        (weights.below_contract, share(below)),
        (weights.availability, share(missing_availability)),
        (weights.reaction, share(late)),
        (weights.incidents, share(frequency)),
    ]


def verdict_of(score: float, weights: ProviderScoreWeights) -> ProviderScoreVerdict:
    return "pass" if score >= weights.pass_pct else "below_norm"


def seconds(value: Any) -> int | None:
    """Whole seconds of an aggregate; the database answers with a float or a Decimal."""
    return None if value is None else int(round(float(value)))


async def reaction_timings(
    session: AsyncSession, selected: Any, *, window: ScoreWindow
) -> dict[int, Timings]:
    """Median and worst time from the start of an incident to its first change of status."""
    first_move = (
        select(IncidentEvent.incident_id, func.min(IncidentEvent.created_at).label("moved_at"))
        .where(IncidentEvent.kind == FIRST_MOVE_KIND)
        .group_by(IncidentEvent.incident_id)
        .subquery()
    )
    answered = extract("epoch", first_move.c.moved_at - Incident.started_at)
    rows = await session.execute(
        select(
            Incident.provider_id.label("provider_id"),
            func.percentile_cont(0.5).within_group(answered).label("median_s"),
            func.max(answered).label("worst_s"),
        )
        .select_from(Incident)
        .join(selected, selected.c.line_id == Incident.line_id)
        .join(first_move, first_move.c.incident_id == Incident.id)
        .where(
            Incident.started_at >= window.start,
            Incident.started_at < window.end,
            # A window the provider announced is not its fault: it drops out of the score (T-70).
            outside_planned_works(Incident.provider_id, Incident.school_id, Incident.started_at),
        )
        .group_by(Incident.provider_id)
    )
    return {
        row.provider_id: Timings(median_s=seconds(row.median_s), worst_s=seconds(row.worst_s))
        for row in rows
    }


async def announced_incidents(
    session: AsyncSession, selected: Any, *, window: ScoreWindow
) -> dict[int, int]:
    """Incidents of the period that started inside a window their own provider had announced.

    They are counted by the analytics of T-45 as everything else is, but they do not weigh on
    the frequency part of the score: the provider warned about that time (ТЗ п. 14).
    """
    rows = await session.execute(
        select(
            Incident.provider_id.label("provider_id"),
            func.count(Incident.id).label("announced_count"),
        )
        .select_from(Incident)
        .join(selected, selected.c.line_id == Incident.line_id)
        .where(
            Incident.started_at >= window.start,
            Incident.started_at < window.end,
            inside_planned_works(Incident.provider_id, Incident.school_id, Incident.started_at),
        )
        .group_by(Incident.provider_id)
    )
    return {row.provider_id: int(row.announced_count) for row in rows}


def line_rows(filters: AnalyticsFilters) -> Select[Any]:
    """Main lines of the selection with their contract and the district of their school."""
    selected = selected_lines(filters).subquery()
    return (
        select(
            Line.id.label("line_id"),
            Line.provider_id,
            Line.contract_down_mbps,
            Line.contract_up_mbps,
            School.id.label("school_id"),
            School.full_name.label("school_name"),
            School.region_id,
            Region.name.label("region_name"),
        )
        .join(selected, selected.c.line_id == Line.id)
        .join(School, School.id == Line.school_id)
        .outerjoin(Region, Region.id == School.region_id)
    )


async def lines_below_norm(
    session: AsyncSession, filters: AnalyticsFilters
) -> dict[int, list[ProviderLineBelowNorm]]:
    """Lines whose contract promises less than the thresholds they are judged by, by provider.

    The comparison is against the profile that applies to the line — its own, its district's or
    the global one (``app/services/thresholds.py``, ADR-004) — never against a number written
    here: a district may be judged by thresholds of its own.
    """
    profiles = await active_threshold_profiles(session)
    found: dict[int, list[ProviderLineBelowNorm]] = {}
    for row in await session.execute(line_rows(filters).order_by(School.full_name)):
        profile = profile_of(profiles, line_id=row.line_id, region_id=row.region_id)
        if profile is None:
            continue
        down = row.contract_down_mbps
        up = row.contract_up_mbps
        below = (down is not None and down < profile.download_min_mbps) or (
            up is not None and up < profile.upload_min_mbps
        )
        if not below:
            continue
        found.setdefault(row.provider_id, []).append(
            ProviderLineBelowNorm(
                line_id=row.line_id,
                school_id=row.school_id,
                school_name=row.school_name,
                region_name=row.region_name,
                contract_down_mbps=down,
                contract_up_mbps=up,
                download_min_mbps=profile.download_min_mbps,
                upload_min_mbps=profile.upload_min_mbps,
            )
        )
    return found


async def counted_schools(session: AsyncSession, filters: AnalyticsFilters) -> dict[int, int]:
    """Schools on the main lines of every provider of the selection."""
    selected = selected_lines(filters).subquery()
    rows = await session.execute(
        select(
            selected.c.provider_id,
            func.count(func.distinct(selected.c.school_id)).label("schools_count"),
        ).group_by(selected.c.provider_id)
    )
    return {row.provider_id: int(row.schools_count) for row in rows}


async def score_rows(
    session: AsyncSession,
    filters: AnalyticsFilters,
    weights: ProviderScoreWeights,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    now: datetime,
) -> tuple[ScoreWindow, float, list[ProviderScoreRow]]:
    """Rows of the providers of the selection, ordered by name as the reports order them."""
    settings = await system_settings(session)
    window = score_window(settings, period, period_from, period_to, now=now)
    # Both reports are asked for exactly the window above, so the two answers are comparable.
    measured = await analytics_report(
        session,
        "provider",
        filters,
        period="custom",
        period_from=window.start,
        period_to=window.end,
        now=now,
    )
    incidents = await incident_analytics_report(
        session,
        "provider",
        filters,
        period="custom",
        period_from=window.start,
        period_to=window.end,
        now=now,
    )
    by_provider = {row.id: row for row in incidents.rows}
    timings = await reaction_timings(session, selected_lines(filters).subquery(), window=window)
    announced = await announced_incidents(
        session, selected_lines(filters).subquery(), window=window
    )
    schools = await counted_schools(session, filters)
    below_norm = await lines_below_norm(session, filters)

    rows = []
    for row in measured.rows:
        if row.id is None or row.name is None:
            continue
        counted = by_provider.get(row.id)
        opened = counted.incidents_count if counted else 0
        reaction = timings.get(row.id, Timings())
        schools_count = schools.get(row.id, 0)
        # The row reports every incident of the period, as the analytics screen does; the
        # penalty counts only those outside the windows the provider announced (T-70).
        parts = penalties(
            row,
            reaction,
            incidents_opened=max(0, opened - announced.get(row.id, 0)),
            schools_count=schools_count,
            weights=weights,
            availability_min_pct=measured.availability_min_pct,
        )
        # Without a single measurement of the period the parts say nothing: an empty score is
        # honest, a hundred out of a hundred would not be.
        score = (
            None
            if not row.measurements_count
            else max(0.0, round(100 - sum(weight * penalty for weight, penalty in parts), 1))
        )
        rows.append(
            ProviderScoreRow(
                id=row.id,
                name=row.name,
                schools_count=schools_count,
                lines_count=counted.lines_count if counted else 0,
                measurements_count=row.measurements_count,
                problem_count=row.problem_count,
                problem_pct=row.problem_pct,
                availability_pct=row.availability_pct,
                below_contract_pct=row.below_contract_pct,
                incidents_opened=opened,
                incidents_closed=counted.restored_count if counted else 0,
                reaction_median_s=reaction.median_s,
                reaction_worst_s=reaction.worst_s,
                restore_avg_s=counted.avg_duration_s if counted else None,
                restore_worst_s=counted.max_duration_s if counted else None,
                lines_below_norm_count=len(below_norm.get(row.id, [])),
                score=score,
                verdict=None if score is None else verdict_of(score, weights),
            )
        )
    return window, measured.availability_min_pct, rows


async def provider_score_report(
    session: AsyncSession,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    region_id: int | None,
    now: datetime,
) -> ProviderScoreReport:
    """One row per provider the user may see (ADR-008), with its score for the period."""
    weights = weights_of(await system_settings(session))
    window, availability_min_pct, rows = await score_rows(
        session,
        AnalyticsFilters(region_id=region_id),
        weights,
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=now,
    )
    return ProviderScoreReport(
        period_from=window.start,
        period_to=window.end,
        weights=weights,
        availability_min_pct=availability_min_pct,
        rows=rows,
    )


async def provider_schools(
    session: AsyncSession,
    provider_id: int,
    window: ScoreWindow,
    *,
    now: datetime,
) -> list[ProviderSchoolRow]:
    """Schools on the main lines of the provider: the numbers of the period and the status now."""
    filters = AnalyticsFilters(provider_id=provider_id)
    report = await analytics_report(
        session,
        "school",
        filters,
        period="custom",
        period_from=window.start,
        period_to=window.end,
        now=now,
    )
    regions = {
        row.school_id: row.region_name
        for row in await session.execute(line_rows(filters).distinct())
    }
    ids = [row.id for row in report.rows if row.id is not None]
    statuses = await school_statuses(session, ids, now=now)
    return [
        ProviderSchoolRow(
            school_id=row.id,
            name=row.name or "",
            region_name=regions.get(row.id),
            status=statuses[row.id],
            measurements_count=row.measurements_count,
            below_contract_pct=row.below_contract_pct,
            availability_pct=row.availability_pct,
            sustained_mismatch=(
                None
                if row.sustained_mismatch_lines_count is None
                else row.sustained_mismatch_lines_count > 0
            ),
        )
        for row in report.rows
        if row.id is not None
    ]


async def provider_score_detail(
    session: AsyncSession,
    provider_id: int,
    *,
    period: AnalyticsPeriod,
    period_from: datetime | None,
    period_to: datetime | None,
    now: datetime,
) -> ProviderScoreDetail:
    """Card of one provider: its row, its schools and the lines below the norm (§6.3).

    A provider without a single visible line answers 404: outside his own lines a district and
    a provider know nothing about him at all (ADR-008).
    """
    weights = weights_of(await system_settings(session))
    filters = AnalyticsFilters(provider_id=provider_id)
    window, availability_min_pct, rows = await score_rows(
        session,
        filters,
        weights,
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=now,
    )
    row = next((candidate for candidate in rows if candidate.id == provider_id), None)
    if row is None:
        raise ApiError(404, "not_found", PROVIDER_NOT_FOUND)
    below_norm = await lines_below_norm(session, filters)
    return ProviderScoreDetail(
        period_from=window.start,
        period_to=window.end,
        weights=weights,
        availability_min_pct=availability_min_pct,
        provider=row,
        appeals_email=await session.scalar(
            select(Provider.appeals_email).where(Provider.id == provider_id)
        ),
        schools=await provider_schools(session, provider_id, window, now=now),
        lines_below_norm=below_norm.get(provider_id, []),
    )
