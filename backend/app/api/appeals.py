"""Appeal API of the panel (plan.md §10 «Обращения»): AI draft, sending, status, PDF.

Contract stubs: every endpoint answers 501 until the task in ``not_implemented`` lands.
The number is assigned by sending, never by a draft (ТЗ п. 17, ADR-011). There is no DELETE:
a sent appeal and its history stay. Appeals are limited by the user's scope from T-20 (ADR-008).
"""

from typing import Any

from fastapi import APIRouter, Response, Security, status

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.appeals import (
    AppealCreate,
    AppealDetail,
    AppealDraft,
    AppealDraftRequest,
    AppealUpdate,
)
from app.schemas.errors import Problem

router = APIRouter(prefix="/appeals", tags=["appeals"], dependencies=[Security(user_token)])

APPEAL_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Обращение не найдено"}


@router.post(
    "/draft",
    summary="AI-черновик обращения поставщику",
    description=(
        "Ничего не сохраняет и номер не присваивает. Контекст собирает сервер, в модель не "
        "уходят ФИО, телефоны и e-mail (ADR-011). Модель недоступна или не настроена — не "
        "ошибка: ai_generated=false, текст — пустой шаблон (T-47). Неизвестный incident_id, "
        "school_id или line_id, линия другой школы — 422."
    ),
)
async def generate_appeal_draft(body: AppealDraftRequest) -> AppealDraft:
    raise not_implemented("T-47")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Отправить обращение: номер, письмо поставщику, PDF",
    description=(
        "Номер присваивается здесь. Контекст сервер пересобирает за тот же период; статус после "
        "отправки — sent_to_provider. SMTP не настроен или у поставщика нет адреса — не ошибка: "
        "delivery_status=not_sent, PDF сохраняется (ADR-011). Неизвестный incident_id, "
        "school_id или line_id, линия другой школы — 422."
    ),
)
async def create_appeal(body: AppealCreate) -> AppealDetail:
    raise not_implemented("T-48")


@router.patch(
    "/{appeal_id}",
    summary="Сменить статус обращения или добавить комментарий",
    description="Переходы — как у инцидентов (T-41); каждое изменение — в appeal_events.",
    responses={
        404: APPEAL_NOT_FOUND,
        409: {
            "model": Problem,
            "description": "Переход в этот статус недопустим (type invalid_status_transition)",
        },
    },
)
async def update_appeal(appeal_id: int, body: AppealUpdate) -> AppealDetail:
    raise not_implemented("T-48")


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
async def get_appeal_pdf(appeal_id: int) -> Response:
    raise not_implemented("T-48")
