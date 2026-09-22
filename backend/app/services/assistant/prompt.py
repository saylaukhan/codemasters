"""Prompts of the assistant (T-84, ADR-017): the rules, the panel of the role, the dialog.

The system prompt is built from the role, the open screen and the language of the person:
the rules of the answer, the profile of the role, the panel as a whole, then the open screen
and every other screen the role can open (``knowledge.py``). The dialog goes into the user
prompt line by line as it went in the panel. All of it is text about the panel: nothing is
read from the database and no fact about a school gets here (ТЗ п. 12).
"""

from collections.abc import Sequence

from app.schemas.assistant import AssistantMessage, AssistantScreen
from app.schemas.statuses import Locale, UserRole
from app.services.assistant.knowledge import COMMON, ROLES, SCREENS, screens_of

# Language of the answer by the language of the panel (T-66); rule 6 names it.
LANGUAGES: dict[Locale, str] = {"ru": "русский", "kk": "казахский"}

WHO = (
    "Ты — помощник по интерфейсу панели Jyldam (мониторинг интернета в школах "
    "Восточно-Казахстанской области). Ты объясняешь, как пользоваться панелью: где какой "
    "раздел, что означают статусы и показатели, как выполнить действие."
)

# What the model may and may not do; the language rule is filled in by ``build_system``.
RULES = (
    "1. Отвечай только по описанию панели ниже. Если ответа в нём нет — скажи об этом и "
    "посоветуй, к кому обратиться: к администратору системы или в районный отдел образования.",
    "2. Ты не видишь данные школ, замеры, инциденты и настройки: не называй цифры, статусы и "
    "события конкретной школы, а объясняй, где их посмотреть.",
    "3. Называй кнопки, разделы и статусы точно так, как они написаны в описании, в кавычках "
    "«»; путь по разделам записывай через стрелку: «Администрирование → Пороги».",
    "4. Учитывай роль пользователя: не предлагай действий, которых у роли нет; если действие "
    "делает другая роль — скажи, какая.",
    "5. Отвечай коротко: 2–6 предложений или нумерованный список шагов. Разметка — только "
    "абзацы, списки «- » и «1. », **жирный** для названий кнопок и разделов; без заголовков, "
    "таблиц и ссылок.",
    "6. Язык ответа — {language}; если вопрос задан на другом языке из двух (русском или "
    "казахском), отвечай на языке вопроса.",
    "7. Вопросы не о панели вежливо отклоняй одной фразой и предложи помощь по панели.",
)

OPEN_SCREEN = "Открыт сейчас"
OTHER_SCREENS = "Другие экраны, доступные пользователю"
DIALOG = "Диалог с пользователем панели; ответь на его последнюю реплику."

# Who wrote a line of the dialog, as the model reads it.
AUTHORS = {"user": "Пользователь", "assistant": "Помощник"}


def build_system(role: UserRole, screen: AssistantScreen, locale: Locale) -> str:
    """System prompt of one question: the rules, the role, the panel, the screens of the role.

    The open screen is described whatever the role — a school user may open the card of an
    incident by its address, and the panel says he is there — and comes first; the other
    screens are the ones the role can open, in the order of the navigation.
    """
    language = LANGUAGES[locale]
    others = [code for code in screens_of(role) if code != screen]
    parts = [
        WHO,
        "",
        "Правила:",
        *(rule.format(language=language) for rule in RULES),
        "",
        f"Пользователь: {ROLES[role]}",
        "",
        "Панель:",
        COMMON,
        "",
        f"{OPEN_SCREEN}: {SCREENS[screen].title}.",
        SCREENS[screen].text,
        "",
        f"{OTHER_SCREENS}:",
    ]
    for code in others:
        parts += ["", f"{SCREENS[code].title}.", SCREENS[code].text]
    return "\n".join(parts)


def build_prompt(messages: Sequence[AssistantMessage]) -> str:
    """The dialog as the model reads it, the question of the person last."""
    lines = [DIALOG]
    for message in messages:
        lines.append(f"{AUTHORS[message.author]}: {message.text.strip()}")
    return "\n\n".join(lines)
