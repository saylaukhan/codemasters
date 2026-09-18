"""School API of the panel (plan.md §10 «Школы»): list, card, devices, lines, points, contacts.

Endpoints of later tasks answer 501 until the task in ``not_implemented`` lands. There is no
DELETE: a school is deactivated with ``is_active`` and keeps its history (ТЗ п. 20). Lists and
cards are limited by the user's scope from T-20 (ADR-008); a school outside it is a 404.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, current_user, require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.core.errors import not_implemented
from app.schemas.devices import DeviceListItemPage
from app.schemas.errors import Problem
from app.schemas.incidents import IncidentListItemPage
from app.schemas.schools import (
    LineCreate,
    LineDetail,
    LineDetailPage,
    LineUpdate,
    MonitoringPointCreate,
    MonitoringPointDetail,
    MonitoringPointDetailPage,
    MonitoringPointUpdate,
    SchoolContactCreate,
    SchoolContactDetail,
    SchoolContactDetailPage,
    SchoolContactUpdate,
    SchoolCreate,
    SchoolDetail,
    SchoolListItemPage,
    SchoolSort,
    SchoolUpdate,
)
from app.schemas.statuses import SchoolStatus
from app.services import references, school_setup
from app.services.school_card import school_contacts, school_detail, school_devices, school_lines
from app.services.schools import SchoolListFilters, school_list

router = APIRouter(
    prefix="/schools", tags=["schools"], dependencies=[Depends(require("schools:read"))]
)

# Right to see the phone of a responsible person (ТЗ п. 15); without it the phone is empty.
PHONE_PERMISSION = "contacts:phone"

SCHOOL_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Школа не найдена"}

MAIN_LINE_EXISTS: dict[str, Any] = {
    "model": Problem,
    "description": "У школы уже есть основная линия (type main_line_exists)",
}

SCHOOL_CODE_TAKEN: dict[str, Any] = {
    "model": Problem,
    "description": "School ID уже занят другой школой (type school_code_taken)",
}


@router.get(
    "",
    summary="Список школ со средними показателями и статусом",
    description=(
        "Фильтры provider_id и connection_type_id отбирают школы, у которых есть такая линия. "
        "Сортировка серверная; без sort — по названию."
    ),
)
async def list_schools(
    params: Annotated[PageParams, Depends(page_params)],
    region_id: int | None = None,
    provider_id: int | None = None,
    connection_type_id: int | None = None,
    status: Annotated[list[SchoolStatus] | None, Query()] = None,
    is_active: Annotated[
        bool | None, Query(description="true — активные, false — отключённые; не задан — все")
    ] = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Название или School ID")
    ] = None,
    period_from: Annotated[
        AwareDatetime | None,
        Query(
            description="Начало окна средних, включительно; по умолчанию — последние 24 ч, "
            "как на главной"
        ),
    ] = None,
    period_to: Annotated[
        AwareDatetime | None,
        Query(description="Конец окна средних, не включая; по умолчанию — текущий момент"),
    ] = None,
    sort: Annotated[
        SchoolSort | None,
        Query(
            description="Поле; «-» — по убыванию. status: normal < unstable < critical < offline, "
            "no_data в конце; -status — сначала худшие"
        ),
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SchoolListItemPage:
    now = datetime.now(UTC)
    period_to = period_to or now
    return await school_list(
        session,
        SchoolListFilters(region_id, provider_id, connection_type_id, status, is_active, q),
        period_from=period_from or period_to - timedelta(hours=24),
        period_to=period_to,
        sort=sort,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "",
    dependencies=[Depends(require("schools:write"))],
    status_code=status.HTTP_201_CREATED,
    summary="Создать школу",
    description="Неизвестный region_id — 422.",
    responses={409: SCHOOL_CODE_TAKEN},
)
async def create_school(
    body: SchoolCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> SchoolDetail:
    school_id = await references.create_school(session, body)
    return await school_detail(session, school_id, now=datetime.now(UTC))


@router.get(
    "/{school_id}",
    summary="Карточка школы: статус и текущие показатели",
    responses={404: SCHOOL_NOT_FOUND},
)
async def get_school(
    school_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> SchoolDetail:
    return await school_detail(session, school_id, now=datetime.now(UTC))


@router.patch(
    "/{school_id}",
    dependencies=[Depends(require("schools:write"))],
    summary="Изменить или деактивировать школу",
    description="Рабочие часы (working_hours) настраиваются в T-37. Неизвестный region_id — 422.",
    responses={404: SCHOOL_NOT_FOUND, 409: SCHOOL_CODE_TAKEN},
)
async def update_school(
    school_id: int,
    body: SchoolUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SchoolDetail:
    changes = await references.update_school(session, school_id, body)
    describe_action(request, changes=changes or None)
    return await school_detail(session, school_id, now=datetime.now(UTC))


@router.get(
    "/{school_id}/devices",
    summary="Компьютеры школы с последними замерами",
    responses={404: SCHOOL_NOT_FOUND},
)
async def list_school_devices(
    school_id: int,
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceListItemPage:
    return await school_devices(session, school_id, params, now=datetime.now(UTC))


@router.get(
    "/{school_id}/lines",
    summary="Линии школы с договорными значениями",
    responses={404: SCHOOL_NOT_FOUND},
)
async def list_school_lines(
    school_id: int,
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LineDetailPage:
    return await school_lines(session, school_id, params, now=datetime.now(UTC))


@router.post(
    "/{school_id}/lines",
    dependencies=[Depends(require("schools:write"))],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить линию школы",
    description="Неизвестный provider_id или connection_type_id — 422.",
    responses={404: SCHOOL_NOT_FOUND, 409: MAIN_LINE_EXISTS},
)
async def create_school_line(
    school_id: int, body: LineCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> LineDetail:
    line_id = await school_setup.create_line(session, school_id, body)
    return await school_setup.school_line(session, school_id, line_id, now=datetime.now(UTC))


@router.patch(
    "/{school_id}/lines/{line_id}",
    dependencies=[Depends(require("schools:write"))],
    summary="Изменить линию школы",
    description="Неизвестный provider_id или connection_type_id — 422.",
    responses={
        404: {"model": Problem, "description": "Школа или линия не найдены"},
        409: MAIN_LINE_EXISTS,
    },
)
async def update_school_line(
    school_id: int,
    line_id: int,
    body: LineUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LineDetail:
    changes = await school_setup.update_line(session, school_id, line_id, body)
    describe_action(request, changes=changes or None)
    return await school_setup.school_line(session, school_id, line_id, now=datetime.now(UTC))


@router.get(
    "/{school_id}/points",
    summary="Точки мониторинга школы с их линиями",
    description="Главная точка — первой.",
    responses={404: SCHOOL_NOT_FOUND},
)
async def list_school_points(
    school_id: int,
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MonitoringPointDetailPage:
    return await school_setup.school_points(session, school_id, params)


@router.post(
    "/{school_id}/points",
    dependencies=[Depends(require("schools:write"))],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить точку мониторинга школы",
    description="Линия другой школы или неизвестная — 422 на line_id.",
    responses={404: SCHOOL_NOT_FOUND},
)
async def create_school_point(
    school_id: int,
    body: MonitoringPointCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MonitoringPointDetail:
    point_id = await school_setup.create_point(session, school_id, body)
    return await school_setup.school_point(session, point_id)


@router.patch(
    "/{school_id}/points/{point_id}",
    dependencies=[Depends(require("schools:write"))],
    summary="Изменить точку мониторинга или привязать её к другой линии",
    description="Линия другой школы или неизвестная — 422 на line_id.",
    responses={404: {"model": Problem, "description": "Школа или точка не найдены"}},
)
async def update_school_point(
    school_id: int,
    point_id: int,
    body: MonitoringPointUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MonitoringPointDetail:
    changes = await school_setup.update_point(session, school_id, point_id, body)
    describe_action(request, changes=changes or None)
    return await school_setup.school_point(session, point_id)


@router.get(
    "/{school_id}/contacts",
    summary="Ответственные лица школы",
    responses={404: SCHOOL_NOT_FOUND},
)
async def list_school_contacts(
    school_id: int,
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> SchoolContactDetailPage:
    return await school_contacts(
        session, school_id, params, show_phone=PHONE_PERMISSION in user.permissions
    )


@router.post(
    "/{school_id}/contacts",
    dependencies=[Depends(require("schools:write"))],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить ответственное лицо школы",
    responses={404: SCHOOL_NOT_FOUND},
)
async def create_school_contact(
    school_id: int,
    body: SchoolContactCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> SchoolContactDetail:
    return await school_setup.create_contact(
        session, school_id, body, show_phone=PHONE_PERMISSION in user.permissions
    )


@router.patch(
    "/{school_id}/contacts/{contact_id}",
    dependencies=[Depends(require("schools:write"))],
    summary="Изменить ответственное лицо школы",
    description="updated_at ставит сервер при каждом изменении.",
    responses={404: {"model": Problem, "description": "Школа или контакт не найдены"}},
)
async def update_school_contact(
    school_id: int,
    contact_id: int,
    body: SchoolContactUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> SchoolContactDetail:
    contact, changes = await school_setup.update_contact(
        session,
        school_id,
        contact_id,
        body,
        show_phone=PHONE_PERMISSION in user.permissions,
    )
    describe_action(request, changes=changes or None)
    return contact


@router.get(
    "/{school_id}/incidents",
    summary="Инциденты школы, новые сверху",
    responses={404: SCHOOL_NOT_FOUND},
)
async def list_school_incidents(
    school_id: int, params: Annotated[PageParams, Depends(page_params)]
) -> IncidentListItemPage:
    raise not_implemented("T-41")
