"""Requests and responses of the letter templates (T-60; ТЗ п. 17, п. 20; ADR-011).

A template is the subject and the body of a letter to the provider with placeholders the server
fills with the facts of the appeal — ``{{school_name}}``, ``{{contract_number}}``,
``{{metrics}}`` — and the instructions the model gets on top of them. The filled template is
the letter the model writes from and the letter the editor opens with when the model is silent.
Two kinds: an ordinary appeal and a formal claim (претензия). One template is the default; a
template is switched off with ``is_active``, never deleted. In a PATCH body an absent field
stays unchanged, ``null`` clears ``ai_instructions``, and ``null`` for any other field is a 422.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page

# Kind of the letter: an appeal asks to fix the service, a claim cites the contract and demands.
type AppealKind = Literal["appeal", "claim"]

SUBJECT_MAX_LENGTH = 255
BODY_MAX_LENGTH = 20000
INSTRUCTIONS_MAX_LENGTH = 2000

# What the server fills a template with, by placeholder name (``{{name}}``): the descriptions
# are shown in the admin panel next to the editor of a template.
PLACEHOLDERS: dict[str, str] = {
    "topic": "«Инцидент INC-…» для обращения по инциденту, иначе «Качество интернет-соединения»",
    "school_code": "School ID школы",
    "school_name": "Название школы",
    "provider_name": "Поставщик",
    "line_identifier": "Идентификатор линии у поставщика",
    "contract_number": "Номер договора",
    "contract_date": "Дата договора",
    "contract_down_mbps": "Download по договору, Мбит/с",
    "contract_up_mbps": "Upload по договору, Мбит/с",
    "period": "Период обращения: начало — конец, с временем",
    "period_dates": "Период обращения: даты начала и конца",
    "period_from": "Начало периода",
    "period_to": "Конец периода",
    "incident_number": "Номер инцидента",
    "measurements_count": "Замеров за период",
    "problem_count": "Замеров с нарушением",
    "outages_count": "Число простоев",
    "outages_duration": "Суммарная длительность простоев",
    "facts": "Блок фактов: School ID, школа, поставщик, линия, договор, период, замеры, простои",
    "metrics": "Блок показателей: факт за период против порога и договора",
    "excerpt": "Выдержка замеров за период",
}

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def unknown_placeholders(text: str) -> list[str]:
    """Names in ``{{…}}`` the server has no value for, in the order of their first use."""
    found: list[str] = []
    for name in PLACEHOLDER.findall(text):
        if name not in PLACEHOLDERS and name not in found:
            found.append(name)
    return found


def check_placeholders(value: str | None) -> str | None:
    if value is not None and (unknown := unknown_placeholders(value)):
        names = ", ".join("{{" + name + "}}" for name in unknown)
        raise ValueError(f"неизвестные подстановки: {names}")
    return value


class AppealPlaceholder(BaseModel):
    """One placeholder a template may use and what the server puts in its place."""

    name: str = Field(examples=["school_name"], description="Имя внутри {{…}}")
    description: str


class AppealPlaceholderList(BaseModel):
    """Every placeholder the server fills, in the order of the letter."""

    items: list[AppealPlaceholder]


class AppealTemplateCreate(BaseModel):
    """New template of a letter; ``is_default`` takes the mark from the current default."""

    name: str = Field(min_length=1, max_length=255, examples=["Претензионное письмо"])
    kind: AppealKind
    subject: str = Field(
        min_length=1,
        max_length=SUBJECT_MAX_LENGTH,
        examples=["Претензия по договору {{contract_number}}: {{school_code}}"],
        description="Тема письма с подстановками {{…}}",
    )
    body: str = Field(
        min_length=1,
        max_length=BODY_MAX_LENGTH,
        description="Текст письма в Markdown с подстановками {{…}}: сервер заполняет их фактами "
        "обращения, модель пишет письмо по заполненному шаблону (ADR-011)",
    )
    ai_instructions: str | None = Field(
        default=None,
        max_length=INSTRUCTIONS_MAX_LENGTH,
        description="Что модель должна учесть сверх фактов: тон, ссылки на договор, требования",
    )
    is_default: bool = Field(
        default=False, description="Шаблон, который черновик берёт без выбора; он один"
    )

    @field_validator("subject", "body")
    @classmethod
    def known_placeholders(cls, value: str) -> str:
        check_placeholders(value)
        return value


class AppealTemplateUpdate(BaseModel):
    """Changes of a template; the default one cannot be switched off."""

    name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    kind: AppealKind | SkipJsonSchema[None] = None
    subject: (
        Annotated[str, Field(min_length=1, max_length=SUBJECT_MAX_LENGTH)] | SkipJsonSchema[None]
    ) = None
    body: Annotated[str, Field(min_length=1, max_length=BODY_MAX_LENGTH)] | SkipJsonSchema[None] = (
        None
    )
    ai_instructions: str | None = Field(default=None, max_length=INSTRUCTIONS_MAX_LENGTH)
    is_default: bool | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("name", "kind", "subject", "body", "is_default", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value

    @field_validator("subject", "body")
    @classmethod
    def known_placeholders(cls, value: str | None) -> str | None:
        return check_placeholders(value)


class AppealTemplateDetail(BaseModel):
    """Template of a letter as the admin panel edits it."""

    id: int
    name: str
    kind: AppealKind
    subject: str = Field(description="Тема письма с подстановками {{…}}")
    body: str = Field(description="Текст письма в Markdown с подстановками {{…}}")
    ai_instructions: str | None
    is_default: bool = Field(description="Черновик без выбора шаблона пишется по нему")
    is_active: bool = Field(description="Отключённый шаблон не предлагается, его письма остаются")
    updated_at: datetime


class AppealTemplateDetailPage(Page[AppealTemplateDetail]):
    """Page of the templates: the default first, then by name."""


class AppealTemplateOption(BaseModel):
    """Template to choose in the editor of a draft (T-47): active ones only."""

    id: int
    name: str
    kind: AppealKind
    is_default: bool


class AppealTemplateOptionPage(Page[AppealTemplateOption]):
    """Active templates, the default first."""
