"""Letter templates of the admin panel (T-86; ТЗ п. 17, п. 20; ADR-011): list, placeholders,
create, change.

There is no DELETE: a template is switched off with ``is_active`` and the appeals written by it
keep the reference. The default template cannot be switched off: a draft always has one to
open with. Templates are edited by the Oblast and Administrator roles; every change goes to
the audit log.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.core.deps import PageParams, page_params
from app.schemas.appeal_templates import (
    AppealPlaceholderList,
    AppealTemplateCreate,
    AppealTemplateDetail,
    AppealTemplateDetailPage,
    AppealTemplateUpdate,
)
from app.schemas.errors import Problem
from app.services import appeal_templates

router = APIRouter(
    prefix="/appeal-templates",
    tags=["admin"],
    dependencies=[Depends(require("appeal_templates:manage"))],
)

TEMPLATE_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Шаблон письма не найден"}
DEFAULT_REQUIRED: dict[str, Any] = {
    "model": Problem,
    "description": "Шаблон по умолчанию нельзя отключить или лишить признака "
    "(type default_template_required)",
}


@router.get(
    "",
    summary="Шаблоны писем поставщику: обращения и претензии",
    description=(
        "Порядок: шаблон по умолчанию, затем по названию. Модель пишет письмо по шаблону, "
        "заполненному фактами обращения; без модели редактор открывается с заполненным шаблоном "
        "(ADR-011)."
    ),
)
async def list_appeal_templates(
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[
        str | None, Query(min_length=1, max_length=255, description="Название или его часть")
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppealTemplateDetailPage:
    return await appeal_templates.template_list(session, params, q=q)


@router.get(
    "/placeholders",
    summary="Подстановки шаблона письма",
    description="Что сервер подставляет вместо {{имя}} в тему и текст шаблона.",
)
async def list_appeal_placeholders() -> AppealPlaceholderList:
    return appeal_templates.placeholders()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать шаблон письма",
    description=(
        "Неизвестная подстановка в теме или тексте — 422 на поле. is_default переносит "
        "признак с прежнего шаблона по умолчанию."
    ),
)
async def create_appeal_template(
    body: AppealTemplateCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> AppealTemplateDetail:
    return await appeal_templates.create_template(session, body)


@router.patch(
    "/{template_id}",
    summary="Изменить или отключить шаблон письма",
    description=(
        "Действует со следующего черновика; отправленные письма не меняются. Шаблон по "
        "умолчанию нельзя отключить или лишить признака — сначала назначьте другой (409)."
    ),
    responses={404: TEMPLATE_NOT_FOUND, 409: DEFAULT_REQUIRED},
)
async def update_appeal_template(
    template_id: int,
    body: AppealTemplateUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppealTemplateDetail:
    template, changes = await appeal_templates.update_template(session, template_id, body)
    describe_action(request, changes=changes or None)
    return template
