"""T-84: the interface assistant through the API — the button, an answer, the bad paths.

The model is a fake provider, so nothing here goes to the network: a socket in this file is
a bug and not a slow test. What is proved is what the panel leans on: the status the button
of the header follows; an answer whose prompt carries the open screen and the role and never
a fact of the database; the 503 of a switched-off assistant, of a model without a key and of
a model that does not answer — ``application/problem+json`` with a detail about the assistant,
not the draft of an appeal and not a 500; the 422 of a dialog that does not end with a
question; and every role of ТЗ п. 16 being allowed to ask, a stranger to the panel not.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ApiError
from app.models import Line
from app.schemas.statuses import UserRole
from app.services.assistant import DISABLED
from app.services.assistant.knowledge import ROLES, SCREENS
from app.services.llm import NO_KEY_DETAIL, NOT_CONFIGURED, UNAVAILABLE
from app.services.llm.base import NO_DRAFT, LLMProvider, not_configured
from tests.factories import bearer, create_school, create_user
from tests.test_admin_incident_rules import ok, problem

STATUS = "/api/assistant"
ASK = "/api/assistant/ask"

# A key of the test: made up, not a secret (AGENTS.md §2.7).
KEY = "test-assistant-key-0123456789"
QUESTION = "Как сообщить о проблеме с интернетом?"
ANSWER = "Нажмите **«Сообщить о проблеме»** в кабинете школы и проверьте письмо."


class FakeProvider(LLMProvider):
    """The model of the test: it answers and remembers what it was asked (T-46)."""

    name = "fake"

    def __init__(self, answer: str = ANSWER, error: ApiError | None = None) -> None:
        self.answer = answer
        self.error = error
        self.prompt = ""
        self.system: str | None = None

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.prompt, self.system = prompt, system
        if self.error is not None:
            raise self.error
        return self.answer


def settings_of(**values: str | bool) -> Settings:
    """Settings of the server with the model and the assistant replaced by ``values``."""
    llm = {"llm_provider": "claude", "llm_api_key": KEY, "llm_model": "", "llm_url": ""}
    return Settings(**{**llm, **values})


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test of the assistant asks the network: the transport of the adapter is not there."""

    def no_network(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("тест не ходит в сеть: модель должна быть подменена")

    monkeypatch.setattr("app.services.llm.base.request_json", no_network)


def configure(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    """Settings the assistant reads, in place of the environment of the test run."""
    monkeypatch.setattr("app.services.assistant.get_settings", lambda: settings)


def model(monkeypatch: pytest.MonkeyPatch, provider: LLMProvider) -> None:
    """Put ``provider`` in the place the assistant takes the model from (``get_provider``)."""
    monkeypatch.setattr("app.services.assistant.get_provider", lambda *args: provider)


def question(screen: str = "school_cabinet", *lines: str) -> dict[str, Any]:
    """Body of a question on ``screen``: the dialog so far and the question last."""
    dialog = list(lines) or [QUESTION]
    messages = [
        {"author": "assistant" if index % 2 == len(dialog) % 2 else "user", "text": text}
        for index, text in enumerate(dialog)
    ]
    return {"screen": screen, "messages": messages}


async def test_the_status_says_whether_the_button_is_shown(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The header shows «Помощник» only when the assistant is on and a model is configured."""
    school = await create_school(session)
    user = bearer(await create_user(session, "school", school_id=school.id))

    configure(monkeypatch, settings_of())
    on = ok(await api_client.get(STATUS, headers=user))
    configure(monkeypatch, settings_of(llm_api_key=""))
    no_key = ok(await api_client.get(STATUS, headers=user))
    configure(monkeypatch, settings_of(assistant_enabled=False))
    off = ok(await api_client.get(STATUS, headers=user))

    assert on == {"available": True, "reason": None}
    assert no_key == {"available": False, "reason": "llm_not_configured"}
    assert off == {"available": False, "reason": "disabled"}


async def test_an_answer_comes_from_the_model_told_the_panel_of_the_role(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The main rule of ADR-017: the screen and the role to the model, the data never."""
    school = await create_school(session)
    user = await create_user(session, "school", school_id=school.id)
    provider = FakeProvider()
    configure(monkeypatch, settings_of())
    model(monkeypatch, provider)

    body = ok(await api_client.post(ASK, json=question(), headers=bearer(user)))

    assert body == {"text": ANSWER}
    assert QUESTION in provider.prompt
    assert provider.system is not None
    assert SCREENS["school_cabinet"].text in provider.system
    assert ROLES["school"] in provider.system
    assert SCREENS["admin"].text not in provider.system
    # Nothing of the database reaches the model: not the school, not the user.
    assert school.school_code not in provider.system
    assert school.full_name not in provider.prompt
    assert user.email not in provider.system
    assert user.email not in provider.prompt


async def test_the_dialog_travels_whole_and_the_answer_language_is_the_profile_one(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Earlier lines go with the question (nothing is stored); Kazakh profile — Kazakh answer."""
    school = await create_school(session)
    user = await create_user(session, "school", school_id=school.id)
    user.locale = "kk"
    await session.flush()
    provider = FakeProvider()
    configure(monkeypatch, settings_of())
    model(monkeypatch, provider)

    ok(
        await api_client.post(
            ASK,
            json=question("appeals", "Где черновики?", "В списке их нет.", "А как создать?"),
            headers=bearer(user),
        )
    )

    assert "Пользователь: Где черновики?" in provider.prompt
    assert "Помощник: В списке их нет." in provider.prompt
    assert provider.prompt.endswith("Пользователь: А как создать?")
    assert provider.system is not None
    assert "Язык ответа — казахский" in provider.system


@pytest.mark.parametrize("broken", ["disabled", "not_configured", "unavailable"])
async def test_a_silent_assistant_is_503_about_the_assistant_not_a_500(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    """Every bad path is problem+json 503 with a detail a person can act on (ADR-009)."""
    school = await create_school(session)
    user = bearer(await create_user(session, "school", school_id=school.id))
    configure(monkeypatch, settings_of(assistant_enabled=broken != "disabled"))
    if broken == "not_configured":

        def raise_not_configured(*args: Any) -> LLMProvider:
            raise not_configured(NO_KEY_DETAIL)

        monkeypatch.setattr("app.services.assistant.get_provider", raise_not_configured)
    else:
        silent = ApiError(503, UNAVAILABLE, f"Модель недоступна (HTTP 502). {NO_DRAFT}")
        model(monkeypatch, FakeProvider(error=silent))

    response = await api_client.post(ASK, json=question(), headers=user)

    expected = {"disabled": DISABLED, "not_configured": NOT_CONFIGURED, "unavailable": UNAVAILABLE}
    body = problem(response, 503, expected[broken])
    assert "Черновик" not in body["detail"]
    if broken == "not_configured":
        assert "LLM_API_KEY" in body["detail"]
    if broken == "unavailable":
        assert "HTTP 502" in body["detail"]


async def test_a_dialog_must_end_with_a_question(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    school = await create_school(session)
    user = bearer(await create_user(session, "school", school_id=school.id))
    configure(monkeypatch, settings_of())
    model(monkeypatch, FakeProvider())

    ends_with_answer = {
        "screen": "appeals",
        "messages": [{"author": "user", "text": QUESTION}, {"author": "assistant", "text": ANSWER}],
    }
    unknown_screen = question("settings")
    for body in (ends_with_answer, unknown_screen, {"screen": "map", "messages": []}):
        response = await api_client.post(ASK, json=body, headers=user)

        errors = problem(response, 422, "validation_error")["errors"]
        assert errors, body
        assert all(error["field"].startswith(("messages", "screen")) for error in errors), body


async def test_every_role_may_ask_and_a_stranger_may_not(
    session: AsyncSession, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``assistant:ask`` belongs to every role of ТЗ п. 16; without a sign-in there is a 401."""
    school = await create_school(session)
    line = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    scopes: dict[UserRole, dict[str, int]] = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": line.provider_id},
        "oblast": {},
        "admin": {},
    }
    provider = FakeProvider()
    configure(monkeypatch, settings_of())
    model(monkeypatch, provider)

    for role, scope in scopes.items():
        user = await create_user(session, role, **scope)
        screen = "school_cabinet" if role == "school" else "schools"

        body = ok(await api_client.post(ASK, json=question(screen), headers=bearer(user)))

        assert body["text"] == ANSWER, role
        assert provider.system is not None
        assert ROLES[role] in provider.system, role

    problem(await api_client.post(ASK, json=question()), 401, "unauthorized")
    problem(await api_client.get(STATUS), 401, "unauthorized")
