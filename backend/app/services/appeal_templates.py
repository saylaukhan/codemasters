"""Templates of the letters to providers in the admin panel (T-86; ТЗ п. 17, п. 20; ADR-011):
list, create, change, and the template a draft is written by.

Exactly one active template is the default: the draft of T-47 takes it when the editor names no
other. Making a template the default takes the mark from the previous one in the same
transaction; the default cannot be switched off or lose the mark by itself, so a draft always
has a template to open with. Nothing is deleted: a switched-off template is not offered, and the
appeals written by it keep the reference. The changed fields are returned for the audit record
(``describe_action``).
"""

from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import AppealTemplate
from app.schemas.appeal_templates import (
    PLACEHOLDERS,
    AppealPlaceholder,
    AppealPlaceholderList,
    AppealTemplateCreate,
    AppealTemplateDetail,
    AppealTemplateDetailPage,
    AppealTemplateOption,
    AppealTemplateOptionPage,
    AppealTemplateUpdate,
)
from app.services.references import Changes, apply_changes, invalid_field, matching, page_of
from app.services.settings import NOT_CONFIGURED

DEFAULT_REQUIRED = "default_template_required"
NO_DEFAULT_DETAIL = (
    "Нет шаблона письма по умолчанию — примените миграции или назначьте шаблон в админке"
)


def template_not_found() -> ApiError:
    return ApiError(404, "not_found", "Шаблон письма не найден")


def placeholders() -> AppealPlaceholderList:
    """Every placeholder a template may use, with what the server puts in its place."""
    return AppealPlaceholderList(
        items=[
            AppealPlaceholder(name=name, description=description)
            for name, description in PLACEHOLDERS.items()
        ]
    )


def template_detail(template: AppealTemplate) -> AppealTemplateDetail:
    return AppealTemplateDetail.model_validate(template, from_attributes=True)


def ordered(query: Select[Any]) -> Select[Any]:
    """The default first, then by name."""
    return query.order_by(AppealTemplate.is_default.desc(), AppealTemplate.name, AppealTemplate.id)


async def template_list(
    session: AsyncSession, params: PageParams, *, q: str | None = None
) -> AppealTemplateDetailPage:
    query = ordered(select(AppealTemplate).where(*matching(q, AppealTemplate.name)))
    rows, total = await page_of(session, query, params)
    return AppealTemplateDetailPage(
        items=[template_detail(row.AppealTemplate) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def template_options(session: AsyncSession, params: PageParams) -> AppealTemplateOptionPage:
    """Templates the editor of a draft may choose from: the active ones, the default first."""
    query = ordered(select(AppealTemplate).where(AppealTemplate.is_active))
    rows, total = await page_of(session, query, params)
    return AppealTemplateOptionPage(
        items=[
            AppealTemplateOption.model_validate(row.AppealTemplate, from_attributes=True)
            for row in rows
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def clear_default(session: AsyncSession, *, except_id: int | None = None) -> None:
    """Take the default mark off the other templates before giving it to one: the partial
    unique index of the table allows one row with it."""
    query = update(AppealTemplate).where(AppealTemplate.is_default)
    if except_id is not None:
        query = query.where(AppealTemplate.id != except_id)
    await session.execute(query.values(is_default=False))


async def create_template(
    session: AsyncSession, body: AppealTemplateCreate
) -> AppealTemplateDetail:
    if body.is_default:
        await clear_default(session)
    template = AppealTemplate(**body.model_dump())
    session.add(template)
    await session.commit()
    # ``is_active`` and the timestamps were set by the database: read them back.
    await session.refresh(template)
    return template_detail(template)


async def update_template(
    session: AsyncSession, template_id: int, body: AppealTemplateUpdate
) -> tuple[AppealTemplateDetail, Changes]:
    template = await session.get(AppealTemplate, template_id)
    if template is None:
        raise template_not_found()
    updates = body.model_dump(exclude_unset=True)
    if template.is_default and updates.get("is_active") is False:
        raise ApiError(
            409,
            DEFAULT_REQUIRED,
            "Шаблон по умолчанию нельзя отключить: сначала назначьте другой шаблон",
        )
    if template.is_default and updates.get("is_default") is False:
        raise ApiError(
            409,
            DEFAULT_REQUIRED,
            "Снять признак «по умолчанию» можно только назначив другой шаблон",
        )
    if updates.get("is_default") and not template.is_default:
        if updates.get("is_active", template.is_active) is False:
            raise invalid_field("is_default", "Шаблон по умолчанию должен действовать")
        await clear_default(session, except_id=template_id)
    changes = apply_changes(template, updates)
    await session.commit()
    await session.refresh(template)
    return template_detail(template), changes


async def template_for_draft(session: AsyncSession, template_id: int | None) -> AppealTemplate:
    """The template a draft is written by: the chosen active one, else the default.

    An unknown or switched-off template is a 422 on ``template_id``; an installation without a
    default is incomplete, so it answers 503, not 500.
    """
    if template_id is None:
        template = await session.scalar(
            select(AppealTemplate).where(AppealTemplate.is_default, AppealTemplate.is_active)
        )
        if template is None:
            raise ApiError(503, NOT_CONFIGURED, NO_DEFAULT_DETAIL)
        return template
    template = await session.get(AppealTemplate, template_id)
    if template is None or not template.is_active:
        raise invalid_field("template_id", "Шаблон письма не найден или отключён")
    return template
