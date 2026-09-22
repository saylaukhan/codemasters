"""Interface assistant of the panel (T-84, ADR-017): is it on, and one question of a dialog.

Every role has ``assistant:ask`` (``app/auth/permissions.py``): the assistant knows the
screens of the panel and no data of anyone, so a stranger learns nothing here (ADR-008).
``POST /ask`` changes nothing and is not audited — the audit reads entities off the path and
finds none (``app/auth/audit.py``) — and the dialog is never written on the server (ТЗ п. 12).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth import AuthUser, current_user, require
from app.schemas.assistant import AssistantAnswer, AssistantQuestion, AssistantStatus
from app.schemas.errors import Problem
from app.services import assistant as service

PERMISSION = "assistant:ask"

router = APIRouter(
    prefix="/assistant", tags=["assistant"], dependencies=[Depends(require(PERMISSION))]
)

UNAVAILABLE: dict[str, Any] = {
    "model": Problem,
    "description": (
        "Помощник выключен, модель не настроена или не ответила "
        "(type assistant_disabled, llm_not_configured, llm_unavailable)"
    ),
}


@router.get(
    "",
    summary="Доступен ли помощник по интерфейсу",
    description=(
        "Панель показывает кнопку «Помощник» в шапке, только когда available=true: помощник "
        "включён (ASSISTANT_ENABLED) и модель ADR-011 настроена. Запроса к модели здесь нет."
    ),
)
async def get_assistant_status() -> AssistantStatus:
    return service.availability()


@router.post(
    "/ask",
    summary="Вопрос помощнику по интерфейсу",
    description=(
        "Диалог целиком и код открытого экрана; последняя реплика — вопрос. Модель получает "
        "описание панели, профиль роли и открытый экран — и ничего из данных школ; ответ — "
        "текст с абзацами, списками и **жирным**. Ничего не сохраняется и в журнал не пишется. "
        "Помощник выключен, модель не настроена или не ответила — 503 problem+json."
    ),
    responses={503: UNAVAILABLE},
)
async def ask_assistant(
    body: AssistantQuestion, user: Annotated[AuthUser, Depends(current_user)]
) -> AssistantAnswer:
    return await service.answer(user, body)
