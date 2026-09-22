"""Choice of the model by the settings of the environment (T-46, ТЗ п. 17, ADR-011).

``LLM_PROVIDER`` says who writes the draft: ``claude`` — the Messages API over the network,
``deepseek`` — the Chat Completions API over the network (T-83), ``ollama`` — a model of a
closed loop next to the server. The key lives only in the environment (``LLM_API_KEY``),
never in the code, in the database or in the panel (ТЗ п. 12).

An installation without a key is a normal installation: the appeals of T-47 ask for a provider
and get a 503 ``llm_not_configured`` in problem+json, the editor opens with an empty template
and the text is written by hand (ADR-011). Nothing here falls with a 500.
"""

from app.core.config import Settings, get_settings
from app.services.llm.base import (
    NOT_CONFIGURED,
    UNAVAILABLE,
    HttpLLMProvider,
    LLMProvider,
    not_configured,
)
from app.services.llm.claude import ClaudeProvider
from app.services.llm.deepseek import DeepSeekProvider
from app.services.llm.ollama import OllamaProvider

__all__ = [
    "NOT_CONFIGURED",
    "UNAVAILABLE",
    "ClaudeProvider",
    "DeepSeekProvider",
    "HttpLLMProvider",
    "LLMProvider",
    "OllamaProvider",
    "get_provider",
    "not_configured",
]

# Names of ``LLM_PROVIDER``; a new model is a new class and a new name here.
PROVIDERS = ("claude", "deepseek", "ollama")

NO_KEY_DETAIL = (
    "Ключ LLM не настроен: задайте LLM_API_KEY в окружении сервера. "
    "Черновик не создан, напишите текст обращения вручную."
)


def unknown_provider_detail(name: str) -> str:
    """Reason of a 503 for a name ``LLM_PROVIDER`` has no class for: an empty one too."""
    chosen = f"«{name}»" if name else "не выбран"
    return (
        f"Провайдер LLM {chosen}: допустимые значения LLM_PROVIDER — {', '.join(PROVIDERS)}. "
        "Черновик не создан, напишите текст обращения вручную."
    )


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Provider of ``LLM_PROVIDER``; ``ApiError`` 503 while the model is not configured."""
    settings = settings or get_settings()
    name = settings.llm_provider.strip().lower()
    if name == "claude":
        if not settings.llm_api_key:
            raise not_configured(NO_KEY_DETAIL)
        return ClaudeProvider(settings.llm_api_key, settings.llm_model, settings.llm_url)
    if name == "deepseek":
        if not settings.llm_api_key:
            raise not_configured(NO_KEY_DETAIL)
        return DeepSeekProvider(settings.llm_api_key, settings.llm_model, settings.llm_url)
    if name == "ollama":
        return OllamaProvider(settings.llm_url, settings.llm_model)
    raise not_configured(unknown_provider_detail(name))
