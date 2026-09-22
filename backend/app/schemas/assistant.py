"""Requests and responses of the interface assistant (T-84, ADR-017).

The assistant answers questions about the panel itself: where a screen is, what a status
means, how an appeal is sent. It never sees the data of the schools: the only context the
panel sends is the code of the open screen, and the only thing that comes back is text. The
dialog lives in the browser and travels whole with every question, so the server stores
nothing of it (ТЗ п. 12).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Screens of the panel the assistant is told about: the sections of ``web/src/app/sections.ts``
# and the cards inside them; ``other`` is an address without a screen of its own.
type AssistantScreen = Literal[
    "overview",
    "map",
    "schools",
    "school_card",
    "school_cabinet",
    "device_card",
    "incidents",
    "incident_card",
    "appeals",
    "appeal_draft",
    "appeal_card",
    "providers",
    "rollout",
    "analytics",
    "exports",
    "admin",
    "other",
]

# Who wrote a line of the dialog: the person or the assistant.
type AssistantAuthor = Literal["user", "assistant"]

# Why the button is not in the header: switched off, or the model of ADR-011 has no key.
type AssistantUnavailableReason = Literal["disabled", "llm_not_configured"]

# One line of the dialog; a question longer than this is not about the panel.
MESSAGE_MAX_LENGTH = 2000
# Lines of the dialog sent with a question: the older ones are left in the browser.
DIALOG_MAX_MESSAGES = 20


class AssistantStatus(BaseModel):
    """Whether the panel shows the button of the assistant (T-84)."""

    available: bool = Field(
        description="Помощник включён и модель настроена: панель показывает кнопку в шапке"
    )
    reason: AssistantUnavailableReason | None = Field(
        default=None, description="Почему недоступен; null — доступен"
    )


class AssistantMessage(BaseModel):
    """One line of the dialog."""

    author: AssistantAuthor
    text: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)


class AssistantQuestion(BaseModel):
    """The open screen and the dialog so far; the last line is the question."""

    screen: AssistantScreen = Field(
        description="Открытый экран панели: помощник отвечает с учётом него"
    )
    messages: list[AssistantMessage] = Field(
        min_length=1,
        max_length=DIALOG_MAX_MESSAGES,
        description="Диалог целиком, последняя реплика — вопрос пользователя",
    )

    @field_validator("messages")
    @classmethod
    def check_last_line_is_a_question(
        cls, messages: list[AssistantMessage]
    ) -> list[AssistantMessage]:
        # A validator of the field, not of the model: the 422 then names ``messages``, where
        # the editor of the panel can show it, instead of the body as a whole.
        if messages[-1].author != "user":
            raise ValueError("последняя реплика должна быть вопросом пользователя")
        return messages


class AssistantAnswer(BaseModel):
    """Answer of the model; nothing is stored (T-84)."""

    text: str = Field(
        description="Ответ помощника: абзацы, списки и **жирный**, как в черновике обращения"
    )
