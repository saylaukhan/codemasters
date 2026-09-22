"""Рассылки сводки для руководителя (T-67, docs/design/README.md §6.2): список, правка, отправка.

Раздел администрирования, поэтому право одно — ``settings:manage``, как у системных настроек:
рассылку заводят Область и Администратор, чья область видимости — вся ВКО (ADR-008). Отдельное
право не вводится, а район, по которому собирается выпуск, задаётся полем ``region_id``.

Предпросмотр и письмо строит один и тот же генератор (``app/services/digest.py``), поэтому
``GET /preview`` отдаёт ровно тот PDF, который уходит по расписанию.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.digests import (
    DigestSendResult,
    DigestSettingsCreate,
    DigestSettingsDetail,
    DigestSettingsDetailPage,
    DigestSettingsUpdate,
)
from app.schemas.errors import Problem
from app.services import digest_admin

router = APIRouter(
    prefix="/digests", tags=["admin"], dependencies=[Depends(require("settings:manage"))]
)

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem, "description": "Рассылка сводки не найдена"}
}
PDF_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
    **NOT_FOUND,
}


@router.get("", summary="Рассылки сводки для руководителя")
async def list_digests(
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DigestSettingsDetailPage:
    return await digest_admin.digest_list(session, params)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать рассылку сводки",
    description=(
        "scope=oblast — выпуск по всей области, scope=region — по одному району, и тогда "
        "обязателен region_id. weekday (1 — понедельник) и hour — в settings.timezone "
        "(Asia/Almaty): расписание хранится в таблице, а не в коде (ТЗ п. 11, п. 20). "
        "Без адресов и без чата Telegram — 422: отправлять некуда."
    ),
)
async def create_digest(
    body: DigestSettingsCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> DigestSettingsDetail:
    return await digest_admin.create_digest(session, body)


@router.patch(
    "/{digest_id}",
    summary="Изменить или отключить рассылку сводки",
    description="Охват рассылки не меняется: для другого района создайте новую рассылку.",
    responses=NOT_FOUND,
)
async def update_digest(
    digest_id: int,
    body: DigestSettingsUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DigestSettingsDetail:
    digest, changes = await digest_admin.update_digest(session, digest_id, body)
    describe_action(request, changes=changes or None)
    return digest


@router.delete(
    "/{digest_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить рассылку сводки",
    description="Рассылка — настройка, а не история: удаление ничего не теряет.",
    responses=NOT_FOUND,
)
async def delete_digest(
    digest_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    await digest_admin.delete_digest(session, digest_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{digest_id}/send-now",
    summary="Отправить сводку сейчас",
    description=(
        "Тот же выпуск, что уходит по расписанию, вне расписания. Каждая попытка каждого "
        "канала пишется в notification_log (ТЗ п. 18): установка без SMTP или без бота "
        "Telegram даёт skipped с причиной, а не ошибку запроса."
    ),
    responses=NOT_FOUND,
)
async def send_digest_now(
    digest_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> DigestSendResult:
    return await digest_admin.send_digest_now(session, digest_id, now=datetime.now(UTC))


@router.get(
    "/{digest_id}/preview",
    response_class=Response,
    summary="Предпросмотр сводки одной страницей PDF",
    description=(
        "Страница A4 выпуска за неделю, которая заканчивается сейчас. Тот же генератор, что "
        "письмо рассылки, поэтому предпросмотр совпадает с PDF."
    ),
    responses=PDF_RESPONSE,
)
async def preview_digest(
    digest_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    pdf, file_name = await digest_admin.digest_preview(session, digest_id, now=datetime.now(UTC))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
