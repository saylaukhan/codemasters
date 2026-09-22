"""Appeal API of the panel (plan.md §10 «Обращения»): AI draft, sending, status, history, PDF.

The draft is built by ``app/services/appeals`` (T-47) by a template of the admin panel — an
appeal or a formal claim (T-60): it stores nothing and assigns no number — the number is given
by sending (ТЗ п. 17, ADR-011). There is no DELETE: a sent appeal and its history stay. Appeals
are limited by the user's scope from T-20 (ADR-008), so the provider sees the appeals of his own
lines and nothing else (T-44).
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, current_user, require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.appeal_templates import AppealTemplateOptionPage
from app.schemas.appeals import (
    AppealCreate,
    AppealDetail,
    AppealDraft,
    AppealDraftRequest,
    AppealListItemPage,
    AppealUpdate,
)
from app.schemas.errors import Problem
from app.schemas.statuses import IncidentStatus
from app.services import appeal_templates
from app.services import appeals as service

router = APIRouter(
    prefix="/appeals", tags=["appeals"], dependencies=[Depends(require("appeals:read"))]
)

APPEAL_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Обращение не найдено"}


@router.post(
    "/draft",
    dependencies=[Depends(require("appeals:create"))],
    summary="AI-черновик обращения поставщику",
    description=(
        "Ничего не сохраняет и номер не присваивает. Письмо пишется по шаблону template_id "
        "(без него — по шаблону по умолчанию, T-60): сервер заполняет шаблон фактами, модель "
        "пишет по нему. Контекст собирает сервер, в модель не уходят ФИО, телефоны и e-mail "
        "(ADR-011). Модель недоступна или не настроена — не ошибка: ai_generated=false, текст — "
        "заполненный шаблон (T-47). Неизвестный incident_id, school_id или line_id, линия "
        "другой школы, неизвестный или отключённый template_id — 422."
    ),
)
async def generate_appeal_draft(
    body: AppealDraftRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> AppealDraft:
    return await service.appeal_draft(session, body, user, now=datetime.now(UTC))


@router.get(
    "/templates",
    dependencies=[Depends(require("appeals:create"))],
    summary="Шаблоны писем для выбора в редакторе черновика",
    description="Только действующие шаблоны, по умолчанию — первым (T-60).",
)
async def list_appeal_template_options(
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppealTemplateOptionPage:
    return await appeal_templates.template_options(session, params)


@router.get(
    "",
    summary="Список отправленных обращений, новые сверху",
    description=(
        "Порядок — по sent_at, новые сверху. Черновиков здесь нет: обращение появляется "
        "после «Отправить» (ТЗ п. 17). Кабинет поставщика читает этот же список."
    ),
)
async def list_appeals(
    params: Annotated[PageParams, Depends(page_params)],
    status: Annotated[
        list[IncidentStatus] | None,
        Query(description="Статусы обращения; несколько — повтором параметра"),
    ] = None,
    school_id: int | None = None,
    provider_id: int | None = None,
    incident_id: int | None = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=32, description="Номер обращения или его часть")
    ] = None,
    period_from: Annotated[
        AwareDatetime | None, Query(description="Начало периода по sent_at, включительно")
    ] = None,
    period_to: Annotated[
        AwareDatetime | None, Query(description="Конец периода по sent_at, не включается")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppealListItemPage:
    filters = service.AppealFilters(
        status, school_id, provider_id, incident_id, q, period_from, period_to
    )
    return await service.appeal_list(session, filters, params)


@router.post(
    "",
    dependencies=[Depends(require("appeals:create"))],
    status_code=status.HTTP_201_CREATED,
    summary="Отправить обращение: номер, письмо поставщику, PDF",
    description=(
        "Номер присваивается здесь. Контекст сервер пересобирает за тот же период; вид письма — "
        "по template_id черновика; статус после отправки — sent_to_provider. SMTP не настроен "
        "или у поставщика нет адреса — не ошибка: delivery_status=not_sent, PDF сохраняется "
        "(ADR-011). Неизвестный incident_id, school_id или line_id, линия другой школы, "
        "неизвестный или отключённый template_id — 422."
    ),
)
async def create_appeal(
    body: AppealCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> AppealDetail:
    return await service.create_appeal(session, body, user, now=datetime.now(UTC))


@router.get(
    "/{appeal_id}",
    summary="Карточка обращения с историей",
    responses={404: APPEAL_NOT_FOUND},
)
async def get_appeal(
    appeal_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> AppealDetail:
    return await service.appeal_detail(session, appeal_id)


@router.patch(
    "/{appeal_id}",
    dependencies=[Depends(require("appeals:update"))],
    summary="Сменить статус обращения или добавить комментарий",
    description=(
        "Переходы — как у инцидентов (T-41); каждое изменение — в appeal_events. Поставщик "
        "двигает свои обращения из кабинета; «Закрыт» ставит пользователь района, области или "
        "администратор (ADR-007). Комментарий без статуса — запись comment в истории."
    ),
    responses={
        404: APPEAL_NOT_FOUND,
        409: {
            "model": Problem,
            "description": "Переход в этот статус недопустим (type invalid_status_transition)",
        },
    },
)
async def update_appeal(
    appeal_id: int,
    body: AppealUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> AppealDetail:
    detail = await service.update_appeal(session, appeal_id, body, user, now=datetime.now(UTC))
    describe_action(request, changes={"status": {"new": detail.status}} if body.status else None)
    return detail


@router.get(
    "/{appeal_id}/pdf",
    summary="PDF отправленного обращения",
    response_class=Response,
    responses={
        200: {
            "description": "PDF-файл обращения",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: APPEAL_NOT_FOUND,
    },
)
async def get_appeal_pdf(
    appeal_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    number, content = await service.appeal_pdf_file(session, appeal_id)
    # The number is Cyrillic, an HTTP header is latin-1: the name goes as RFC 5987 (ADR-009).
    name = f"{number}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="appeal.pdf"; '
            f"filename*=UTF-8''{quote(name)}"
        },
    )
