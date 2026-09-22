"""Which thresholds a line is judged by: the most specific active profile wins (ADR-004).

The chain is the line, then the district of its school, then the global profile, which carries
the base values of ТЗ п. 11 and is created by the migration of T-17, so it always answers. The
same chain gives an agent its configuration (T-17) and the server the thresholds of a
measurement on receipt (T-18), so it is written once here. ``most_specific`` orders any such
chain — schedules are looked up by it too.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ThresholdProfile

# Scopes of a threshold profile, from the narrowest to the widest (ADR-004).
PROFILE_SCOPES = ["line", "district", "global"]


def most_specific(statement: Select[Any], scopes: list[str], scope_column: Any) -> Select[Any]:
    """Order the rows of the chain so that the narrowest scope comes first; ``scopes`` is it."""
    order = case({scope: position for position, scope in enumerate(scopes)}, value=scope_column)
    return statement.order_by(order).limit(1)


async def threshold_profile(
    session: AsyncSession, *, line_id: int | None, region_id: int | None
) -> ThresholdProfile | None:
    """Active profile of the line: its own, else its district's, else the global one.

    Without a line the chain starts at the district, without a district at the global profile:
    that is what a chart over several lines is marked with (T-27).

    ``None`` means the installation has no global profile, which the migration of T-17 creates:
    the caller answers 503, not 500 — the database is incomplete, the request is not bad.
    """
    return await session.scalar(
        most_specific(
            select(ThresholdProfile).where(
                ThresholdProfile.is_active,
                or_(
                    ThresholdProfile.scope == "global",
                    (ThresholdProfile.scope == "district")
                    & (ThresholdProfile.region_id == region_id),
                    (ThresholdProfile.scope == "line") & (ThresholdProfile.line_id == line_id),
                ),
            ),
            PROFILE_SCOPES,
            ThresholdProfile.scope,
        )
    )


async def active_threshold_profiles(session: AsyncSession) -> list[ThresholdProfile]:
    """Every active profile at once, for a list of lines judged together (T-68).

    A screen that compares the contract of hundreds of lines with the thresholds that apply to
    them would otherwise ask ``threshold_profile`` once per line. There are few profiles — the
    global one, the districts and the exceptions — so they are read once and matched in memory
    by ``profile_of``, which repeats the chain of ``threshold_profile`` exactly.
    """
    return list(await session.scalars(select(ThresholdProfile).where(ThresholdProfile.is_active)))


def profile_of(
    profiles: Sequence[ThresholdProfile], *, line_id: int | None, region_id: int | None
) -> ThresholdProfile | None:
    """The profile of the line among ``profiles``: its own, else its district's, else global."""
    matching = [
        profile
        for profile in profiles
        if (profile.scope == "global")
        or (profile.scope == "district" and profile.region_id == region_id)
        or (profile.scope == "line" and profile.line_id == line_id)
    ]
    if not matching:
        return None
    return min(matching, key=lambda profile: PROFILE_SCOPES.index(profile.scope))
