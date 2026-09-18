"""Export API (plan.md §10 «Экспорт», ТЗ п. 9): create an export, list them, download a file.

Raw measurements (T-30) and aggregates per school (T-31) are built within the POST; a PDF
report of a school (T-32) and an export of more rows than the settings allow go to the Celery
worker (T-33): the POST answers ``pending``, the GET answers 202 until the file is ready.
Exports cover only the user's scope (ADR-008); an export and its file are served only to the
user who made it. The work is in ``app/services/exports/``.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, current_user, require
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.core.errors import ApiError
from app.schemas.errors import Problem
from app.schemas.exports import ExportCreate, ExportFormat, ExportJob, ExportJobPage
from app.services.exports import create_export as build_export
from app.services.exports import fail_export, owned_export, user_exports
from app.services.exports.files import MEDIA_TYPES

router = APIRouter(
    prefix="/exports", tags=["exports"], dependencies=[Depends(require("exports:create"))]
)

FILE_SCHEMA = {"schema": {"type": "string", "format": "binary"}}

logger = logging.getLogger(__name__)

QUEUE_UNAVAILABLE = "Очередь фоновых выгрузок недоступна, попробуйте позже"


def enqueue_build(export_id: int) -> None:
    """Hand a pending export to the Celery worker. The task is imported here: the Celery app
    reads the settings when it is created, and the API imports without them (tests replace
    this function)."""
    from app.workers.tasks.exports import build_export_task

    build_export_task.delay(export_id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать выгрузку: режим, формат, период, фильтры, колонки",
    description=(
        "Сочетания режима и формата: `raw` — замеры в xlsx, csv или json, фильтры device_ids и "
        "statuses, выбор колонок (T-30); `aggregates` — строка на школу в xlsx, csv или json: "
        "school_code, school_name, measurements_count, avg_download_mbps, min_download_mbps, "
        "avg_upload_mbps, avg_ping_ms, problem_count, problem_pct — по основной линии без Wi‑Fi, "
        "как GET /api/analytics (T-31); `school_report` — PDF по одной школе: шапка с School ID и "
        "периодом, KPI основной линии без Wi‑Fi, графики по дням, число и суммарная "
        "длительность простоев из outages, таблица всех замеров школы со статусами по-русски "
        "(T-32). Другие сочетания — 422. Неизвестные "
        "или вне области видимости school_ids и device_ids — 422 (ADR-008). Выгрузка до "
        "settings.export_sync_max_rows строк (по умолчанию 10 000) формируется в запросе и "
        "приходит ready; PDF и выгрузки больше порога приходят pending и формируются в фоне "
        "(T-33), состояние — GET /api/exports/{id} и список GET /api/exports; очередь "
        "недоступна — выгрузка приходит failed. Файлы raw: в xlsx и csv — русские "
        "заголовки, статусы словами, дата ДД.ММ.ГГГГ и время по settings.timezone "
        "(Asia/Almaty); csv — UTF-8 с BOM, разделитель «;», десятичная запятая; в json — коды "
        "колонок и значений, дата и время ISO. Строки — по названию школы, затем по времени "
        "замера."
    ),
)
async def create_export(
    body: ExportCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> ExportJob:
    now = datetime.now(UTC)
    export = await build_export(session, user.id, body, now=now)
    if export.status == "pending":
        try:
            enqueue_build(export.id)
        except Exception:
            # Redis is down or refuses the task: no worker will ever build this file.
            logger.exception("export %s: not handed to Celery", export.id)
            await fail_export(session, export.id, QUEUE_UNAVAILABLE, now=now)
    return ExportJob.model_validate(export, from_attributes=True)


@router.get(
    "",
    summary="Выгрузки пользователя со статусами, новые сверху",
    description=(
        "Только выгрузки текущего пользователя с неистёкшим expires_at: pending — файл "
        "готовится в фоне, ready — файл по GET /api/exports/{id}, failed — причина в error. "
        "Панель повторяет запрос, пока в списке есть pending (T-33)."
    ),
)
async def list_exports(
    params: Annotated[PageParams, Depends(page_params)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> ExportJobPage:
    return await user_exports(session, user.id, params, now=datetime.now(UTC))


@router.get(
    "/{export_id}",
    response_class=Response,
    summary="Файл выгрузки или её состояние",
    description=(
        "Ответ зависит от status выгрузки: ready — 200 с файлом и Content-Disposition; "
        "pending — 202 с выгрузкой, запрос повторяется позже; failed — 409. Выгрузки другого "
        "пользователя, неизвестные и с истёкшим expires_at — 404. Файл отдаётся только с "
        "Authorization: Bearer: панель скачивает его запросом, а не прямой ссылкой."
    ),
    responses={
        200: {
            "description": "Файл выгрузки",
            "headers": {
                "Content-Disposition": {
                    "description": "attachment с именем файла",
                    "schema": {"type": "string"},
                }
            },
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FILE_SCHEMA,
                "text/csv": FILE_SCHEMA,
                "application/json": FILE_SCHEMA,
                "application/pdf": FILE_SCHEMA,
            },
        },
        202: {"model": ExportJob, "description": "Файл ещё формируется (status pending)"},
        404: {"model": Problem, "description": "Выгрузка не найдена или срок хранения истёк"},
        409: {
            "model": Problem,
            "description": "Файл не сформирован (type export_failed), причина — в detail",
        },
    },
)
async def get_export(
    export_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthUser, Depends(current_user)],
) -> Response:
    export = await owned_export(session, export_id, user.id, now=datetime.now(UTC))
    if export.status == "pending":
        job = ExportJob.model_validate(export, from_attributes=True)
        return JSONResponse(job.model_dump(mode="json"), status_code=status.HTTP_202_ACCEPTED)
    if export.status == "failed" or export.content is None:
        raise ApiError(409, "export_failed", export.error or "Файл выгрузки не сформирован")
    return Response(
        export.content,
        media_type=MEDIA_TYPES[cast(ExportFormat, export.format)],
        headers={"Content-Disposition": f'attachment; filename="{export.file_name}"'},
    )
