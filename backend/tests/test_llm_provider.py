"""T-46: the adapter of the model — one method, a choice by a setting, a key that stays hidden.

Nothing here goes to the network and nothing here needs a database: the only outgoing call of
the adapter (``request_json``) is replaced for the whole module, so a socket in these tests is
a bug and not a slow test. What is proved is the contract the appeals of T-47 will lean on: a
draft is asked from an ``LLMProvider`` and not from Claude, the implementation is chosen by
``LLM_PROVIDER``, and a fake provider takes the place of both without the caller noticing.

The two rules of ADR-011 are proved on the two bad paths. An installation without a key
answers 503 ``llm_not_configured`` in ``application/problem+json`` — with a reason a person can
act on, not a traceback — and a model that refuses or does not answer never carries the key
into the log or into the answer, even when the network error quotes it back.
"""

import logging
import urllib.error
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.errors import PROBLEM_MEDIA_TYPE, ApiError, register_error_handlers
from app.services.llm import NOT_CONFIGURED, UNAVAILABLE, get_provider
from app.services.llm.base import MAX_OUTPUT_TOKENS, SECRET_MASK, LLMProvider
from app.services.llm.claude import ANTHROPIC_VERSION, DEFAULT_MODEL, ClaudeProvider
from app.services.llm.deepseek import DeepSeekProvider
from app.services.llm.ollama import OllamaProvider

# A key of the test: made up, not a secret (AGENTS.md §2.7).
KEY = "test-llm-key-0123456789"
PROMPT = "Школа 12345, договор 100 Мбит/с, факт 12 Мбит/с. Напиши обращение провайдеру."
DRAFT = "Уважаемый поставщик услуг, просим устранить несоответствие скорости."
SYSTEM_PROMPT = "Ты пишешь официальные обращения к поставщику связи от имени школы."
LOGGER = "app.services.llm.base"


class Call:
    """The one request the provider made, as the fake transport saw it."""

    def __init__(self) -> None:
        self.url = ""
        self.payload: dict[str, Any] = {}
        self.headers: dict[str, str] = {}


def answers(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> Call:
    """Replace the transport of the adapter with one that answers ``body`` and remembers how."""
    call = Call()

    def fake(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        call.url, call.payload, call.headers = url, payload, headers
        return body

    monkeypatch.setattr("app.services.llm.base.request_json", fake)
    return call


def fails(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Replace the transport with one that fails the way the network fails."""

    def fake(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        raise error

    monkeypatch.setattr("app.services.llm.base.request_json", fake)


def deepseek_answer(text: str) -> dict[str, Any]:
    """Answer of the Chat Completions API with one choice, the way DeepSeek shapes it."""
    message = {"role": "assistant", "content": text}
    return {"choices": [{"index": 0, "message": message, "finish_reason": "stop"}]}


def no_network(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Transport no test asked for: a request here means the fake was not installed."""
    raise AssertionError("тест не ходит в сеть: транспорт адаптера должен быть подменён")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.llm.base.request_json", no_network)


def settings_of(**values: str) -> Settings:
    """Settings of the server with the whole environment of the LLM replaced by ``values``.

    Every variable of the model is set here, including the ones the test does not name: a
    developer with his own ``.env`` must get the same result as a clean checkout.
    """
    llm = {"llm_provider": "", "llm_api_key": "", "llm_model": "", "llm_url": "", **values}
    return Settings(**llm)


class FakeProvider(LLMProvider):
    """The provider T-47 will put in place of the model: it answers and remembers the prompt."""

    name = "fake"

    def __init__(self, answer: str = DRAFT) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.prompts.append(prompt)
        return self.answer


async def draft(provider: LLMProvider, prompt: str) -> str:
    """A caller of the adapter: it knows the interface and never the implementation."""
    return await provider.generate(prompt)


async def test_a_fake_provider_replaces_the_model() -> None:
    """The call goes through the adapter: a caller of ``LLMProvider`` sees no difference."""
    provider = FakeProvider()

    assert await draft(provider, PROMPT) == DRAFT
    assert provider.prompts == [PROMPT]


async def test_claude_is_chosen_by_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LLM_PROVIDER=claude`` asks the Messages API and returns its text blocks."""
    call = answers(monkeypatch, {"content": [{"type": "text", "text": DRAFT}]})
    provider = get_provider(settings_of(llm_provider="claude", llm_api_key=KEY))

    assert isinstance(provider, ClaudeProvider)
    assert await draft(provider, PROMPT) == DRAFT
    assert call.url == "https://api.anthropic.com/v1/messages"
    assert call.headers["x-api-key"] == KEY
    assert call.headers["anthropic-version"] == ANTHROPIC_VERSION
    assert call.payload["model"] == DEFAULT_MODEL
    assert call.payload["messages"] == [{"role": "user", "content": PROMPT}]


async def test_ollama_is_chosen_by_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LLM_PROVIDER=ollama`` asks the model of the closed loop at its own address."""
    call = answers(monkeypatch, {"response": f"{DRAFT}\n"})
    provider = get_provider(
        settings_of(llm_provider="ollama", llm_url="http://ollama:11434", llm_model="qwen2.5")
    )

    assert isinstance(provider, OllamaProvider)
    assert await draft(provider, PROMPT) == DRAFT
    assert call.url == "http://ollama:11434/api/generate"
    assert call.payload == {"model": "qwen2.5", "prompt": PROMPT, "stream": False}
    assert "x-api-key" not in call.headers


async def test_deepseek_is_chosen_by_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LLM_PROVIDER=deepseek`` asks the Chat Completions API with the key as a bearer token."""
    call = answers(monkeypatch, deepseek_answer(f"{DRAFT}\n"))
    provider = get_provider(settings_of(llm_provider="deepseek", llm_api_key=KEY))

    assert isinstance(provider, DeepSeekProvider)
    assert await draft(provider, PROMPT) == DRAFT
    assert call.url == "https://api.deepseek.com/chat/completions"
    assert call.headers["Authorization"] == f"Bearer {KEY}"
    assert "x-api-key" not in call.headers
    assert call.payload["model"] == "deepseek-chat"
    assert call.payload["messages"] == [{"role": "user", "content": PROMPT}]
    assert call.payload["max_tokens"] == MAX_OUTPUT_TOKENS
    assert call.payload["stream"] is False


async def test_deepseek_sends_the_system_prompt_as_the_first_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The system prompt of T-47 goes first with the role ``system``; address and model as set."""
    call = answers(monkeypatch, deepseek_answer(DRAFT))
    provider = get_provider(
        settings_of(
            llm_provider="deepseek",
            llm_api_key=KEY,
            llm_model="deepseek-reasoner",
            llm_url="https://llm.example.kz/v1/",
        )
    )

    assert await provider.generate(PROMPT, system=SYSTEM_PROMPT) == DRAFT
    assert call.url == "https://llm.example.kz/v1/chat/completions"
    assert call.payload["model"] == "deepseek-reasoner"
    assert call.payload["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": PROMPT},
    ]
    assert "system" not in call.payload


async def test_without_a_key_the_service_answers_problem_json() -> None:
    """No key — 503 problem+json with a reason, not a 500 and not a traceback."""
    application = FastAPI()
    register_error_handlers(application)

    @application.get("/draft")
    async def endpoint() -> str:
        return await get_provider(settings_of(llm_provider="claude", llm_api_key="")).generate(
            PROMPT
        )

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/draft")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    problem = response.json()
    assert problem["type"] == NOT_CONFIGURED
    assert problem["status"] == 503
    assert "LLM_API_KEY" in problem["detail"]
    assert problem["instance"] == "/draft"


@pytest.mark.parametrize("name", ["claude", "deepseek"])
async def test_every_provider_behind_a_key_needs_the_key(name: str) -> None:
    """Both providers of the network answer the same 503 while ``LLM_API_KEY`` is empty."""
    with pytest.raises(ApiError) as raised:
        get_provider(settings_of(llm_provider=name, llm_api_key=""))

    assert raised.value.status == 503
    assert raised.value.type == NOT_CONFIGURED
    assert "LLM_API_KEY" in (raised.value.detail or "")


async def test_an_unknown_provider_is_a_problem_too() -> None:
    """A typo in ``LLM_PROVIDER`` names the allowed values instead of falling."""
    with pytest.raises(ApiError) as raised:
        get_provider(settings_of(llm_provider="gpt", llm_api_key=KEY))

    assert raised.value.status == 503
    assert raised.value.type == NOT_CONFIGURED
    assert "«gpt»" in (raised.value.detail or "")
    assert "claude, deepseek, ollama" in (raised.value.detail or "")


@pytest.mark.parametrize("name", ["claude", "deepseek"])
async def test_the_key_never_reaches_the_log_or_the_answer(
    name: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A network error that quotes the key back leaves it in neither the log nor the answer."""
    fails(monkeypatch, urllib.error.URLError(f"ключ {KEY} отклонён"))
    provider = get_provider(settings_of(llm_provider=name, llm_api_key=KEY))

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(ApiError) as raised:
            await draft(provider, PROMPT)

    assert raised.value.status == 503
    assert raised.value.type == UNAVAILABLE
    assert KEY not in (raised.value.detail or "")
    assert SECRET_MASK in (raised.value.detail or "")
    assert KEY not in caplog.text
    assert KEY not in repr(provider)
    assert caplog.records


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("claude", {"content": [{"type": "tool_use", "id": "toolu_1"}]}),
        # ``deepseek-reasoner`` that spent every token on thinking: reasoning, no letter.
        ("deepseek", {"choices": [{"message": {"content": None, "reasoning_content": "…"}}]}),
        ("deepseek", {"choices": []}),
    ],
)
async def test_a_refusal_of_the_model_is_not_a_crash(
    name: str, body: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An answer without text is an unavailable model, not a 500 in the middle of a draft."""
    answers(monkeypatch, body)
    provider = get_provider(settings_of(llm_provider=name, llm_api_key=KEY))

    with pytest.raises(ApiError) as raised:
        await draft(provider, PROMPT)

    assert raised.value.status == 503
    assert raised.value.type == UNAVAILABLE
    assert "вручную" in (raised.value.detail or "")
