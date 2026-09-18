"""Lines, monitoring points and contacts of a school in the admin panel (T-35, ТЗ п. 10, п. 14,
п. 15).

A school has at most one main line: a second one is a 409 until the first becomes reserve or is
switched off. A monitoring point is bound to a line of the same school (a composite foreign key,
ADR-005); the primary point is one per school, so a new primary one takes the mark from the old.
Nothing is deleted: a line is switched off with ``status = disabled`` and keeps its measurements.

Changed fields go to the audit record (``describe_action``) as JSON; the name, phone and e-mail
of a contact are personal data (ТЗ п. 15) and the log is never cleaned, so only the fact of their
change is kept. ``updated_at`` of a contact is set by the database on every change.
"""

from datetime import datetime
from typing import Any, cast

from pydantic_core import to_jsonable_python
from sqlalchemy import Select, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import ConnectionType, Device, Line, MonitoringPoint, Provider, SchoolContact
from app.schemas.schools import (
    LineCreate,
    LineDetail,
    LineUpdate,
    MonitoringPointCreate,
    MonitoringPointDetail,
    MonitoringPointDetailPage,
    MonitoringPointUpdate,
    SchoolContactCreate,
    SchoolContactDetail,
    SchoolContactUpdate,
)
from app.services.references import Changes, apply_changes, invalid_field
from app.services.school_card import (
    contact_detail,
    ensure_school,
    line_details,
    line_rows,
)

# Fields of a contact whose values stay out of the audit log (ТЗ п. 15).
PERSONAL_FIELDS = frozenset({"full_name", "phone", "email"})
HIDDEN = "***"


def jsonable(changes: Changes) -> Changes:
    """Changes with dates, times and networks as JSON values: ``audit_log.changes`` is JSONB."""
    return cast(Changes, to_jsonable_python(changes))


def main_line_exists() -> ApiError:
    return ApiError(
        409,
        "main_line_exists",
        "У школы уже есть основная линия: сначала сделайте её резервной или отключите",
    )


# --- Lines ---------------------------------------------------------------------------------


async def ensure_references(
    session: AsyncSession, provider_id: int | None, connection_type_id: int | None
) -> None:
    """422 on the field of an unknown provider or connection type."""
    if provider_id is not None and await session.get(Provider, provider_id) is None:
        raise invalid_field("provider_id", "Поставщик не найден")
    if (
        connection_type_id is not None
        and await session.get(ConnectionType, connection_type_id) is None
    ):
        raise invalid_field("connection_type_id", "Тип подключения не найден")


async def ensure_no_other_main(session: AsyncSession, school_id: int, line_id: int | None) -> None:
    query = select(Line.id).where(Line.school_id == school_id, Line.status == "main")
    if line_id is not None:
        query = query.where(Line.id != line_id)
    if await session.scalar(query.limit(1)) is not None:
        raise main_line_exists()


async def school_line(
    session: AsyncSession, school_id: int, line_id: int, *, now: datetime
) -> LineDetail:
    rows = (
        await session.execute(line_rows().where(Line.id == line_id, Line.school_id == school_id))
    ).all()
    return (await line_details(session, rows, now=now))[0]


async def create_line(session: AsyncSession, school_id: int, body: LineCreate) -> int:
    """Id of the new line of the school."""
    await ensure_school(session, school_id)
    await ensure_references(session, body.provider_id, body.connection_type_id)
    if body.status == "main":
        await ensure_no_other_main(session, school_id, None)
    line = Line(school_id=school_id, **body.model_dump())
    session.add(line)
    await session.commit()
    return line.id


async def update_line(
    session: AsyncSession, school_id: int, line_id: int, body: LineUpdate
) -> Changes:
    """Changed fields of the line; ``status = disabled`` switches it off, history stays."""
    await ensure_school(session, school_id)
    line = await session.scalar(select(Line).where(Line.id == line_id, Line.school_id == school_id))
    if line is None:
        raise ApiError(404, "not_found", "Линия не найдена")
    await ensure_references(session, body.provider_id, body.connection_type_id)
    if body.status == "main" and line.status != "main":
        await ensure_no_other_main(session, school_id, line_id)
    changes = apply_changes(line, body.model_dump(exclude_unset=True))
    await session.commit()
    return jsonable(changes)


# --- Monitoring points ---------------------------------------------------------------------


async def ensure_school_line(session: AsyncSession, school_id: int, line_id: int) -> None:
    found = await session.scalar(
        select(Line.id).where(Line.id == line_id, Line.school_id == school_id)
    )
    if found is None:
        raise invalid_field("line_id", "Линия не найдена у этой школы")


async def take_primary(session: AsyncSession, school_id: int, point_id: int | None) -> None:
    """Take the primary mark from the other points of the school before giving it to one."""
    query = update(MonitoringPoint).where(
        MonitoringPoint.school_id == school_id, MonitoringPoint.is_primary
    )
    if point_id is not None:
        query = query.where(MonitoringPoint.id != point_id)
    await session.execute(query.values(is_primary=False))


def point_rows() -> Select[Any]:
    """Rows of ``MonitoringPoint, line_status, provider_name, devices_count``."""
    devices = (
        select(Device.monitoring_point_id, func.count().label("devices_count"))
        .where(Device.status == "active")
        .group_by(Device.monitoring_point_id)
        .subquery()
    )
    return (
        select(
            MonitoringPoint,
            Line.status.label("line_status"),
            Provider.name.label("provider_name"),
            func.coalesce(devices.c.devices_count, 0).label("devices_count"),
        )
        .join(Line, Line.id == MonitoringPoint.line_id)
        .join(Provider, Provider.id == Line.provider_id)
        .outerjoin(devices, devices.c.monitoring_point_id == MonitoringPoint.id)
    )


def point_detail(row: Any) -> MonitoringPointDetail:
    point: MonitoringPoint = row.MonitoringPoint
    return MonitoringPointDetail(
        id=point.id,
        school_id=point.school_id,
        line_id=point.line_id,
        line_status=row.line_status,
        provider_name=row.provider_name,
        name=point.name,
        room=point.room,
        is_primary=point.is_primary,
        devices_count=row.devices_count,
    )


async def school_points(
    session: AsyncSession, school_id: int, params: PageParams
) -> MonitoringPointDetailPage:
    """Monitoring points of the school, the primary one first (ТЗ п. 10)."""
    await ensure_school(session, school_id)
    query = point_rows().where(MonitoringPoint.school_id == school_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.execute(
            query.order_by(
                case((MonitoringPoint.is_primary, 0), else_=1),
                MonitoringPoint.name,
                MonitoringPoint.id,
            )
            .offset(params.offset)
            .limit(params.page_size)
        )
    ).all()
    return MonitoringPointDetailPage(
        items=[point_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def school_point(session: AsyncSession, point_id: int) -> MonitoringPointDetail:
    row = (await session.execute(point_rows().where(MonitoringPoint.id == point_id))).one()
    return point_detail(row)


async def create_point(session: AsyncSession, school_id: int, body: MonitoringPointCreate) -> int:
    """Id of the new monitoring point of the school."""
    await ensure_school(session, school_id)
    await ensure_school_line(session, school_id, body.line_id)
    if body.is_primary:
        await take_primary(session, school_id, None)
    point = MonitoringPoint(school_id=school_id, **body.model_dump())
    session.add(point)
    await session.commit()
    return point.id


async def update_point(
    session: AsyncSession, school_id: int, point_id: int, body: MonitoringPointUpdate
) -> Changes:
    """Changed fields of the point; a new line moves the measurements of its computers there."""
    await ensure_school(session, school_id)
    point = await session.scalar(
        select(MonitoringPoint).where(
            MonitoringPoint.id == point_id, MonitoringPoint.school_id == school_id
        )
    )
    if point is None:
        raise ApiError(404, "not_found", "Точка мониторинга не найдена")
    if body.line_id is not None:
        await ensure_school_line(session, school_id, body.line_id)
    if body.is_primary:
        await take_primary(session, school_id, point_id)
    changes = apply_changes(point, body.model_dump(exclude_unset=True))
    await session.commit()
    return jsonable(changes)


# --- Contacts ------------------------------------------------------------------------------


def hide_personal(changes: Changes) -> Changes:
    return {
        name: {"old": HIDDEN, "new": HIDDEN} if name in PERSONAL_FIELDS else change
        for name, change in changes.items()
    }


async def create_contact(
    session: AsyncSession, school_id: int, body: SchoolContactCreate, *, show_phone: bool
) -> SchoolContactDetail:
    await ensure_school(session, school_id)
    contact = SchoolContact(school_id=school_id, **body.model_dump())
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact_detail(contact, show_phone=show_phone)


async def update_contact(
    session: AsyncSession,
    school_id: int,
    contact_id: int,
    body: SchoolContactUpdate,
    *,
    show_phone: bool,
) -> tuple[SchoolContactDetail, Changes]:
    """The contact after the change and the changed fields, personal values hidden."""
    await ensure_school(session, school_id)
    contact = await session.scalar(
        select(SchoolContact).where(
            SchoolContact.id == contact_id, SchoolContact.school_id == school_id
        )
    )
    if contact is None:
        raise ApiError(404, "not_found", "Контакт не найден")
    changes = apply_changes(contact, body.model_dump(exclude_unset=True))
    await session.commit()
    # ``updated_at`` was set by the database: read it back.
    await session.refresh(contact)
    return contact_detail(contact, show_phone=show_phone), hide_personal(jsonable(changes))
