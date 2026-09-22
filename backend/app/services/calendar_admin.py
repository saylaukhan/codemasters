"""Календарь в админке (T-70, docs/design/README.md §6.5): список, правка, импорт из таблицы.

CRUD повторяет дом остальных настроек (``config_admin.py``, ``digest_admin.py``): список с
наименованиями цели, создание, PATCH только присутствующих полей, изменённые поля — в журнал
аудита. Удаление есть: событие календаря — это настройка, а не история, и миграция T-70 выдаёт
роли панели DELETE на одну эту таблицу.

Импорт читает CSV: в репозитории нет читателя XLSX и заводить зависимость ради приказа об
осенних каникулах не нужно (AGENTS.md §2.6). Дата ``YYYY-MM-DD`` — целые местные сутки
``settings.timezone``, последний день включается целиком; момент ``YYYY-MM-DDTHH:MM`` берётся
как есть. Строка, которую прочитать не удалось, не останавливает импорт: она возвращается в
``errors``, остальные события заводятся.
"""

import csv
import io
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import CalendarEvent, Provider, Region, School
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventDetail,
    CalendarEventDetailPage,
    CalendarEventUpdate,
    CalendarImportRequest,
    CalendarImportResult,
    CalendarKind,
    CalendarScope,
)
from app.services.references import Changes, apply_changes, ensure_region, invalid_field, page_of
from app.services.settings import system_settings

NOT_FOUND = "Событие календаря не найдено"

# Колонки файла импорта; ``school_code``, ``region_code`` и ``comment`` не обязательны.
REQUIRED_COLUMNS = ("kind", "title", "start", "end")
KINDS: tuple[CalendarKind, ...] = ("vacation", "holiday", "planned_works")

# Сколько строк читается из одного файла: приказ по области — это десятки строк, не тысячи.
IMPORT_MAX_ROWS = 1000


def event_rows() -> Select[Any]:
    """События с наименованиями района, школы и поставщика."""
    return (
        select(
            CalendarEvent,
            Region.name.label("region_name"),
            School.full_name.label("school_name"),
            Provider.name.label("provider_name"),
        )
        .outerjoin(Region, Region.id == CalendarEvent.region_id)
        .outerjoin(School, School.id == CalendarEvent.school_id)
        .outerjoin(Provider, Provider.id == CalendarEvent.provider_id)
    )


def event_detail(row: Any) -> CalendarEventDetail:
    event: CalendarEvent = row.CalendarEvent
    return CalendarEventDetail.model_validate(
        {
            "id": event.id,
            "kind": event.kind,
            "scope": event.scope,
            "region_id": event.region_id,
            "region_name": row.region_name,
            "school_id": event.school_id,
            "school_name": row.school_name,
            "provider_id": event.provider_id,
            "provider_name": row.provider_name,
            "starts_at": event.starts_at,
            "ends_at": event.ends_at,
            "title": event.title,
            "comment": event.comment,
        }
    )


async def event_row(session: AsyncSession, event_id: int) -> Any:
    row = (await session.execute(event_rows().where(CalendarEvent.id == event_id))).one_or_none()
    if row is None:
        raise ApiError(404, "not_found", NOT_FOUND)
    return row


async def calendar_list(
    session: AsyncSession,
    params: PageParams,
    kind: CalendarKind | None,
    period_from: datetime | None,
    period_to: datetime | None,
) -> CalendarEventDetailPage:
    """События календаря, ближайшие сверху; фильтры — тип и период."""
    query = event_rows().order_by(CalendarEvent.starts_at.desc(), CalendarEvent.id.desc())
    if kind is not None:
        query = query.where(CalendarEvent.kind == kind)
    if period_from is not None:
        query = query.where(CalendarEvent.ends_at > period_from)
    if period_to is not None:
        query = query.where(CalendarEvent.starts_at <= period_to)
    rows, total = await page_of(session, query, params)
    return CalendarEventDetailPage(
        items=[event_detail(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def ensure_target(session: AsyncSession, body: CalendarEventCreate) -> None:
    """Район, школа и поставщик события существуют; иначе 422 по полю (ADR-009)."""
    if body.region_id is not None:
        await ensure_region(session, body.region_id)
    if body.school_id is not None and await session.get(School, body.school_id) is None:
        raise invalid_field("school_id", "Школа не найдена")
    if body.provider_id is not None and await session.get(Provider, body.provider_id) is None:
        raise invalid_field("provider_id", "Поставщик не найден")


async def create_event(session: AsyncSession, body: CalendarEventCreate) -> CalendarEventDetail:
    await ensure_target(session, body)
    event = CalendarEvent(**body.model_dump())
    session.add(event)
    await session.commit()
    return event_detail(await event_row(session, event.id))


async def update_event(
    session: AsyncSession, event_id: int, body: CalendarEventUpdate
) -> tuple[CalendarEventDetail, Changes]:
    """Период, название и комментарий события; тип и цель не меняются — заведите другое."""
    event: CalendarEvent = (await event_row(session, event_id)).CalendarEvent
    updates = body.model_dump(exclude_unset=True)
    starts_at = updates.get("starts_at", event.starts_at)
    ends_at = updates.get("ends_at", event.ends_at)
    if ends_at <= starts_at:
        raise invalid_field("ends_at", "Конец периода должен быть позже начала")
    changes = apply_changes(event, updates)
    await session.commit()
    return event_detail(await event_row(session, event_id)), changes


async def delete_event(session: AsyncSession, event_id: int) -> None:
    """Событие можно удалить: это настройка, а не история (миграция T-70)."""
    event: CalendarEvent = (await event_row(session, event_id)).CalendarEvent
    await session.delete(event)
    await session.commit()


def parse_moment(value: str, zone: ZoneInfo, *, closing: bool) -> datetime:
    """Момент из ячейки файла: дата — целые местные сутки, дата со временем — этот момент."""
    text = value.strip()
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"не дата и не момент: {text!r}") from None
    if moment.tzinfo is not None:
        return moment
    if len(text) == 10:
        # Последний день приказа входит в каникулы целиком, поэтому концом стоит его полночь.
        day = moment.date() + (timedelta(days=1) if closing else timedelta())
        return datetime.combine(day, time(), tzinfo=zone)
    return moment.replace(tzinfo=zone)


async def import_target(
    session: AsyncSession, row: dict[str, str]
) -> tuple[CalendarScope, int | None, int | None]:
    """Цель строки файла: код школы, код района или, без обоих, вся область."""
    school_code = (row.get("school_code") or "").strip()
    region_code = (row.get("region_code") or "").strip()
    if school_code:
        school_id = await session.scalar(select(School.id).where(School.school_code == school_code))
        if school_id is None:
            raise ValueError(f"школа {school_code!r} не найдена")
        return "school", None, school_id
    if region_code:
        region_id = await session.scalar(select(Region.id).where(Region.code == region_code))
        if region_id is None:
            raise ValueError(f"район {region_code!r} не найден")
        return "district", region_id, None
    return "oblast", None, None


async def import_calendar(
    session: AsyncSession, body: CalendarImportRequest
) -> CalendarImportResult:
    """Заполнить календарь из таблицы CSV; читается заголовок, а не порядок колонок."""
    settings = await system_settings(session)
    zone = ZoneInfo(settings.timezone)
    reader = csv.DictReader(io.StringIO(body.text))
    if reader.fieldnames is None or not set(REQUIRED_COLUMNS) <= set(reader.fieldnames):
        raise invalid_field("text", f"Нужны колонки: {', '.join(REQUIRED_COLUMNS)}")
    created = 0
    errors: list[str] = []
    for number, row in enumerate(reader, start=2):
        if number > IMPORT_MAX_ROWS + 1:
            errors.append(f"строка {number}: файл длиннее {IMPORT_MAX_ROWS} строк, хвост пропущен")
            break
        try:
            kind = (row.get("kind") or "").strip()
            if kind not in KINDS:
                raise ValueError(f"тип {kind!r} неизвестен")
            title = (row.get("title") or "").strip()
            if not title:
                raise ValueError("пустое название")
            starts_at = parse_moment(row["start"], zone, closing=False)
            ends_at = parse_moment(row["end"], zone, closing=True)
            if ends_at <= starts_at:
                raise ValueError("конец периода не позже начала")
            scope, region_id, school_id = await import_target(session, row)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"строка {number}: {error}")
            continue
        session.add(
            CalendarEvent(
                kind=kind,
                scope=scope,
                region_id=region_id,
                school_id=school_id,
                starts_at=starts_at,
                ends_at=ends_at,
                title=title,
                comment=(row.get("comment") or "").strip() or None,
            )
        )
        created += 1
    await session.commit()
    return CalendarImportResult(created=created, errors=errors)
