"""T-84: what the assistant is told — the panel of the role, never the data (ADR-017).

Nothing here needs a database or a model: the system prompt is built from the role, the open
screen and the language alone, and the availability is read from the settings. What is proved
is the rule of ADR-017: the model gets the rules, the profile of the role, the panel and the
screens the role can open — the open one first — and not a word about any school; the dialog
goes in as it went in the panel, the question of the person last.
"""

from typing import get_args

import pytest

from app.core.config import Settings
from app.schemas.assistant import AssistantMessage, AssistantScreen
from app.schemas.statuses import Locale, UserRole
from app.services.assistant import availability
from app.services.assistant.knowledge import COMMON, ROLES, SCREENS, screens_of
from app.services.assistant.prompt import (
    DIALOG,
    OPEN_SCREEN,
    OTHER_SCREENS,
    build_prompt,
    build_system,
)

# A key of the test: made up, not a secret (AGENTS.md §2.7).
KEY = "test-assistant-key-0123456789"


def settings_of(**values: str | bool) -> Settings:
    """Settings with the whole environment of the model and of the assistant replaced."""
    llm = {"llm_provider": "", "llm_api_key": "", "llm_model": "", "llm_url": ""}
    return Settings(**{**llm, **values})


def test_every_screen_and_every_role_is_described() -> None:
    """A screen of the contract without a paragraph would be answered from nothing."""
    assert set(SCREENS) == set(get_args(AssistantScreen.__value__))
    assert set(ROLES) == set(get_args(UserRole.__value__))
    for screen in SCREENS.values():
        assert screen.roles, screen.title


def test_the_system_prompt_holds_the_role_the_panel_and_the_screens_of_the_role() -> None:
    """A school user is told about the cabinet and the appeals, not about the administration."""
    system = build_system("school", "school_cabinet", "ru")

    assert ROLES["school"] in system
    assert COMMON in system
    assert SCREENS["school_cabinet"].text in system
    assert SCREENS["appeals"].text in system
    assert SCREENS["admin"].text not in system
    assert SCREENS["overview"].text not in system
    assert "Пороги" in system


def test_the_open_screen_comes_first_and_the_others_follow_the_navigation() -> None:
    """The screen the person looks at is marked and stands before every other one."""
    system = build_system("admin", "exports", "ru")

    open_at = system.index(f"{OPEN_SCREEN}: {SCREENS['exports'].title}.")
    others_at = system.index(f"{OTHER_SCREENS}:")
    assert open_at < others_at < system.index(SCREENS["overview"].text)
    # Every screen of the role is there once: the open one is not repeated among the others.
    assert system.count(SCREENS["exports"].text) == 1
    for code in screens_of("admin"):
        assert SCREENS[code].text in system


def test_a_screen_opened_by_address_is_described_whatever_the_role() -> None:
    """The rights of a role stay (T-61): a school user on an incident card gets that card."""
    system = build_system("school", "incident_card", "ru")

    assert SCREENS["incident_card"].text in system
    assert "incident_card" not in screens_of("school")


@pytest.mark.parametrize(("locale", "language"), [("ru", "русский"), ("kk", "казахский")])
def test_the_language_of_the_answer_is_the_language_of_the_panel(
    locale: Locale, language: str
) -> None:
    system = build_system("district", "overview", locale)

    assert f"Язык ответа — {language}" in system


def test_the_prompt_is_the_dialog_with_the_question_last() -> None:
    messages = [
        AssistantMessage(author="user", text="Где посмотреть замеры?"),
        AssistantMessage(author="assistant", text="В кабинете, ссылка «Все замеры»."),
        AssistantMessage(author="user", text=" А за месяц? "),
    ]

    prompt = build_prompt(messages)

    assert prompt.startswith(DIALOG)
    assert "Пользователь: Где посмотреть замеры?" in prompt
    assert "Помощник: В кабинете, ссылка «Все замеры»." in prompt
    assert prompt.endswith("Пользователь: А за месяц?")


def test_the_knowledge_names_no_person_and_no_address() -> None:
    """Text about the panel only: no e-mail, no phone, no name of a person (ТЗ п. 12)."""
    everything = "\n".join([COMMON, *ROLES.values(), *(screen.text for screen in SCREENS.values())])

    assert "@" not in everything
    assert "+7" not in everything


def test_the_assistant_is_available_only_switched_on_and_with_a_model() -> None:
    """The button of the header follows this answer (T-84)."""
    off = availability(settings_of(assistant_enabled=False, llm_provider="claude", llm_api_key=KEY))
    no_key = availability(settings_of(llm_provider="claude"))
    on = availability(settings_of(llm_provider="deepseek", llm_api_key=KEY))
    closed_loop = availability(settings_of(llm_provider="ollama"))

    assert (off.available, off.reason) == (False, "disabled")
    assert (no_key.available, no_key.reason) == (False, "llm_not_configured")
    assert (on.available, on.reason) == (True, None)
    assert closed_loop.available is True
