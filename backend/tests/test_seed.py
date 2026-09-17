"""Seed (T-04, T-05): VKO districts, test schools inside them, settings; repeatable runs."""

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, MonitoringPoint, Region, School, SystemSettings
from app.seed import seed, seed_settings

SEEDED_TABLES = (
    "regions",
    "providers",
    "connection_types",
    "schools",
    "lines",
    "monitoring_points",
)


async def row_versions(session: AsyncSession) -> dict[str, str | None]:
    """Physical row addresses per table: an UPDATE of a row writes a new version at a new ctid."""
    return {
        table: await session.scalar(
            text(f"SELECT string_agg(ctid::text, ',' ORDER BY id) FROM {table}")
        )
        for table in SEEDED_TABLES
    }


async def test_repeated_seed_changes_nothing(session: AsyncSession) -> None:
    first = await seed(session)
    versions = await row_versions(session)

    second = await seed(session)

    assert first.lines_created == first.points_created == first.schools
    assert (second.lines_created, second.points_created) == (0, 0)
    # No row was inserted, deleted or rewritten by the second run.
    assert await row_versions(session) == versions


async def test_every_region_has_a_valid_boundary(session: AsyncSession) -> None:
    result = await seed(session)

    invalid = await session.scalars(
        select(Region.code).where(Region.geom.is_(None) | ~func.ST_IsValid(Region.geom))
    )

    assert list(invalid) == []
    assert await session.scalar(select(func.count()).select_from(Region)) == result.regions


async def test_every_school_point_lies_inside_its_region(session: AsyncSession) -> None:
    await seed(session)

    outside = await session.scalars(
        select(School.school_code)
        .join(Region, Region.id == School.region_id)
        .where(School.geom.is_(None) | ~func.ST_Covers(Region.geom, School.geom))
        .order_by(School.school_code)
    )

    assert list(outside) == []


async def test_every_school_has_a_main_line_and_a_primary_point(session: AsyncSession) -> None:
    await seed(session)

    incomplete = await session.scalars(
        select(School.school_code)
        .outerjoin(Line, (Line.school_id == School.id) & (Line.status == "main"))
        .outerjoin(
            MonitoringPoint,
            (MonitoringPoint.line_id == Line.id) & MonitoringPoint.is_primary,
        )
        .where(MonitoringPoint.id.is_(None))
        .order_by(School.school_code)
    )

    assert list(incomplete) == []


async def test_seed_creates_settings_once_and_keeps_admin_changes(session: AsyncSession) -> None:
    created = await seed_settings(session, "http://speedtest.test:8080", "ws://speedtest.test:8081")
    await session.execute(
        update(SystemSettings).values(librespeed_url="https://speedtest.example.kz", ndt7_url=None)
    )

    created_again = await seed_settings(session, "http://other.test:8080", "")

    row = (await session.scalars(select(SystemSettings))).one()
    assert (created, created_again) == (True, False)
    assert (row.librespeed_url, row.ndt7_url) == ("https://speedtest.example.kz", None)


async def test_seed_settings_without_ndt7_stores_no_fallback(session: AsyncSession) -> None:
    await seed_settings(session, "http://speedtest.test:8080", "")

    assert await session.scalar(select(SystemSettings.ndt7_url)) is None
