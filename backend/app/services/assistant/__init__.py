"""Answer of the interface assistant (T-84, ADR-017): the model of ADR-011, told the panel.

``availability`` is what the panel asks before it shows the button in the header: the switch
of the environment and a configured model, without a request to the model. ``answer`` builds
the system prompt of the role, the screen and the language (``prompt.py``), renders the
dialog and asks the provider of ``LLM_PROVIDER``. A model that is not configured or does not
answer leaves as the 503 of the adapter in ``application/problem+json`` (ADR-009), never as a
500 — only the ``detail`` written for the appeals is replaced by one about the assistant.
Nothing is stored: the dialog belongs to the browser, and the audit sees no entity in
``POST /api/assistant/ask`` (``app/auth/audit.py``), so no question is written anywhere.
"""

from http import HTTPStatus

from app.auth.deps import AuthUser
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.schemas.assistant import AssistantAnswer, AssistantQuestion, AssistantStatus
from app.services.assistant.prompt import build_prompt, build_system
from app.services.llm import NOT_CONFIGURED, get_provider
from app.services.llm.base import NO_DRAFT

__all__ = ["DISABLED", "answer", "availability", "disabled"]

# Stable ``type`` of the problem+json of a switched-off assistant (ADR-009).
DISABLED = "assistant_disabled"

DISABLED_DETAIL = "Помощник по интерфейсу выключен: ASSISTANT_ENABLED=false в окружении сервера."
NO_MODEL_DETAIL = (
    "Модель не настроена: задайте LLM_API_KEY в окружении сервера. "
    "Помощник по интерфейсу недоступен."
)
NO_ANSWER = "Помощник не ответил, попробуйте ещё раз."


def disabled() -> ApiError:
    """Error of an installation that switched the assistant off."""
    return ApiError(HTTPStatus.SERVICE_UNAVAILABLE, DISABLED, DISABLED_DETAIL)


def assistant_detail(error: ApiError) -> str:
    """``detail`` of the adapter's 503, said about the assistant instead of a draft."""
    if error.type == NOT_CONFIGURED:
        return NO_MODEL_DETAIL
    reason = (error.detail or "").replace(NO_DRAFT, "").strip()
    return f"{reason} {NO_ANSWER}".strip()


def availability(settings: Settings | None = None) -> AssistantStatus:
    """Whether the panel shows the button: switched on and a model configured (T-84)."""
    settings = settings or get_settings()
    if not settings.assistant_enabled:
        return AssistantStatus(available=False, reason="disabled")
    try:
        get_provider(settings)
    except ApiError as error:
        if error.type != NOT_CONFIGURED:
            raise
        return AssistantStatus(available=False, reason="llm_not_configured")
    return AssistantStatus(available=True)


async def answer(
    user: AuthUser, body: AssistantQuestion, settings: Settings | None = None
) -> AssistantAnswer:
    """Answer of the model to the last line of the dialog, with the panel in its prompt."""
    settings = settings or get_settings()
    if not settings.assistant_enabled:
        raise disabled()
    try:
        provider = get_provider(settings)
        text = await provider.generate(
            build_prompt(body.messages),
            system=build_system(user.role, body.screen, user.locale),
        )
    except ApiError as error:
        # Every 503 of this call comes from the adapter (ADR-011): the same code, a detail
        # about the assistant; anything else is not ours to rewrite.
        if error.status != HTTPStatus.SERVICE_UNAVAILABLE:
            raise
        raise ApiError(error.status, error.type, assistant_detail(error)) from error
    return AssistantAnswer(text=text.strip())
