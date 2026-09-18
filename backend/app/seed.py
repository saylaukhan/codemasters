"""``make seed`` entry point: ``python -m app.seed``.

Loads reference data and local test data (T-04): districts and cities of VKO with boundaries,
providers, connection types and test schools, each with one main line and one primary
monitoring point. Rows are upserted by natural keys (region code, provider name, connection
type code, School ID), lines and points are created only for a school that has none, so a
repeated run changes nothing. The row of ``settings`` gets the measurement server addresses from
the environment (T-05) only when it does not exist: after that they change in the admin panel.
Dev users of the five roles (T-20) are created with the password ``Password1`` — the seed loads
test data and is for local databases only; an existing user is left as is. Data files and their
sources: ``app/seed_data/README.md``.
"""

import asyncio
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import exists, func, select, tuple_
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_engine, get_session_factory
from app.core.security import hash_password
from app.models import (
    ConnectionType,
    Line,
    MonitoringPoint,
    Provider,
    Region,
    School,
    SystemSettings,
    User,
    UserScope,
)

DATA_DIR = Path(__file__).resolve().parent / "seed_data"
REGIONS_FILE = DATA_DIR / "regions.geojson"
SCHOOLS_FILE = DATA_DIR / "schools.csv"

CONNECTION_TYPES = {
    "fiber": "Оптоволокно",
    "adsl": "ADSL",
    "radio": "Радиоканал",
    "satellite": "Спутник",
    "mobile": "Мобильная сеть",
}
POINT_NAME = "Кабинет информатики"

# Dev users of AGENTS.md §7: one per role; Район/город, Школа and Провайдер are scoped to
# Усть-Каменогорск, its first test school and the provider of that school.
DEV_PASSWORD = "Password1"
DEV_REGION_CODE = "UK"
DEV_SCHOOL_CODE = "VKO-UK-001"
DEV_USERS = {
    "admin@example.kz": ("admin", "Администратор системы"),
    "oblast@example.kz": ("oblast", "Специалист областного управления"),
    "rayon@example.kz": ("district", "Специалист отдела образования Усть-Каменогорска"),
    "school@example.kz": ("school", "Ответственный школы VKO-UK-001"),
    "provider@example.kz": ("provider", "Служба поддержки провайдера"),
}


@dataclass(frozen=True)
class SeedResult:
    """What a seed run loaded and what it had to create."""

    regions: int
    providers: int
    connection_types: int
    schools: int
    lines_created: int
    points_created: int


def upsert(model: Any, rows: list[dict[str, Any]], key: str) -> Insert:
    """INSERT … ON CONFLICT (key) DO UPDATE that touches a row only when a value differs."""
    stmt = insert(model).values(rows)
    columns = [column for column in rows[0] if column != key]
    table = model.__table__.c
    return stmt.on_conflict_do_update(
        index_elements=[key],
        set_={**{column: stmt.excluded[column] for column in columns}, "updated_at": func.now()},
        where=tuple_(*(table[column] for column in columns)).is_distinct_from(
            tuple_(*(stmt.excluded[column] for column in columns))
        ),
    )


async def seed(session: AsyncSession) -> SeedResult:
    """Load reference data and test schools into the session's transaction (no commit)."""
    features = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))["features"]
    with SCHOOLS_FILE.open(encoding="utf-8", newline="") as file:
        schools = list(csv.DictReader(file))

    region_rows = [
        {
            "code": feature["properties"]["code"],
            "name": feature["properties"]["name"],
            "geom": func.ST_GeomFromGeoJSON(json.dumps(feature["geometry"])),
        }
        for feature in features
    ]
    await session.execute(upsert(Region, region_rows, "code"))

    connection_type_rows = [{"code": code, "name": name} for code, name in CONNECTION_TYPES.items()]
    await session.execute(upsert(ConnectionType, connection_type_rows, "code"))

    provider_names = sorted({school["provider"] for school in schools})
    await session.execute(
        insert(Provider)
        .values([{"name": name} for name in provider_names])
        .on_conflict_do_nothing(index_elements=["name"])
    )

    region_ids = dict((await session.execute(select(Region.code, Region.id))).tuples().all())
    provider_ids = dict((await session.execute(select(Provider.name, Provider.id))).tuples().all())
    connection_type_ids = dict(
        (await session.execute(select(ConnectionType.code, ConnectionType.id))).tuples().all()
    )

    school_rows = [
        {
            "school_code": school["school_code"],
            "full_name": school["full_name"],
            "region_id": region_ids[school["region_code"]],
            "address": school["address"],
            "geom": WKTElement(f"POINT({school['longitude']} {school['latitude']})", srid=4326),
        }
        for school in schools
    ]
    await session.execute(upsert(School, school_rows, "school_code"))

    by_code = {school["school_code"]: school for school in schools}
    without_lines = await session.execute(
        select(School.id, School.school_code).where(
            School.school_code.in_(by_code), ~exists().where(Line.school_id == School.id)
        )
    )
    line_rows = [
        {
            "school_id": school_id,
            "provider_id": provider_ids[by_code[code]["provider"]],
            "connection_type_id": connection_type_ids[by_code[code]["connection_type"]],
            "contract_down_mbps": float(by_code[code]["contract_down_mbps"]),
            "contract_up_mbps": float(by_code[code]["contract_up_mbps"]),
            "status": "main",
        }
        for school_id, code in without_lines.tuples()
    ]
    if line_rows:
        await session.execute(insert(Line).values(line_rows))

    without_points = await session.execute(
        select(Line.school_id, func.min(Line.id))
        .join(School, School.id == Line.school_id)
        .where(
            School.school_code.in_(by_code),
            Line.status == "main",
            ~exists().where(MonitoringPoint.school_id == Line.school_id),
        )
        .group_by(Line.school_id)
    )
    point_rows = [
        {"school_id": school_id, "line_id": line_id, "name": POINT_NAME, "is_primary": True}
        for school_id, line_id in without_points.tuples()
    ]
    if point_rows:
        await session.execute(insert(MonitoringPoint).values(point_rows))

    return SeedResult(
        regions=len(region_rows),
        providers=len(provider_names),
        connection_types=len(connection_type_rows),
        schools=len(school_rows),
        lines_created=len(line_rows),
        points_created=len(point_rows),
    )


async def seed_settings(session: AsyncSession, librespeed_url: str, ndt7_url: str) -> bool:
    """Create the ``settings`` row with the measurement servers unless it exists (no commit).

    An existing row is left as is: the admin panel may have changed it. An empty ``ndt7_url``
    means no fallback server. Returns whether the row was created.
    """
    result = await session.execute(
        insert(SystemSettings)
        .values(id=1, librespeed_url=librespeed_url, ndt7_url=ndt7_url or None)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(SystemSettings.id)
    )
    return result.scalar_one_or_none() is not None


async def seed_users(session: AsyncSession) -> int:
    """Create the missing dev users with their scopes (no commit); returns how many were new.

    Needs the test schools of ``seed``: the scopes point at them.
    """
    school_id, provider_id = (
        await session.execute(
            select(School.id, Line.provider_id)
            .join(Line, (Line.school_id == School.id) & (Line.status == "main"))
            .where(School.school_code == DEV_SCHOOL_CODE)
        )
    ).one()
    region_id = await session.scalar(select(Region.id).where(Region.code == DEV_REGION_CODE))
    scopes: dict[str, dict[str, int | None]] = {
        "district": {"region_id": region_id},
        "school": {"school_id": school_id},
        "provider": {"provider_id": provider_id},
    }
    existing = set(await session.scalars(select(User.email).where(User.email.in_(DEV_USERS))))
    created = 0
    for email, (role, full_name) in DEV_USERS.items():
        if email in existing:
            continue
        user = User(
            email=email, full_name=full_name, role=role, password_hash=hash_password(DEV_PASSWORD)
        )
        session.add(user)
        await session.flush()
        if role in scopes:
            session.add(UserScope(user_id=user.id, **scopes[role]))
        created += 1
    await session.flush()
    return created


async def run() -> tuple[SeedResult, bool, int]:
    """Seed the database from ``Settings.database_url`` in one transaction."""
    settings = get_settings()
    async with get_session_factory()() as session:
        result = await seed(session)
        settings_created = await seed_settings(session, settings.speedtest_url, settings.ndt7_url)
        users_created = await seed_users(session)
        await session.commit()
    await get_engine().dispose()
    return result, settings_created, users_created


def main() -> int:
    """Run the seed and report what was loaded."""
    result, settings_created, users_created = asyncio.run(run())
    sys.stdout.write(
        f"seed: районов и городов — {result.regions}, провайдеров — {result.providers}, "
        f"типов подключения — {result.connection_types}, тестовых школ — {result.schools}; "
        f"создано линий — {result.lines_created}, точек мониторинга — {result.points_created}; "
        f"системные настройки — {'созданы' if settings_created else 'уже есть, не изменены'}; "
        f"создано dev-пользователей — {users_created}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
