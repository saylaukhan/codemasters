"""Календарь каникул, праздников и плановых работ в админке (T-70, docs/design/README.md §6.5).

Одно событие — один период тишины: в каникулы и праздники доступность не считается и инциденты
не создаются, окно плановых работ вдобавок не входит в оценку поставщика (ТЗ п. 14). Границы
каникул и праздника — целые местные сутки ``settings.timezone``; окно работ задаётся с точностью
до минуты. В теле PATCH отсутствующее поле остаётся как было, ``null`` — 422.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.pagination import Page

# Тип события: каникулы, праздник, плановые работы поставщика.
type CalendarKind = Literal["vacation", "holiday", "planned_works"]

# Область действия события: вся область, район или город, одна школа.
type CalendarScope = Literal["oblast", "district", "school"]

type CalendarTitle = Annotated[
    str, Field(min_length=1, max_length=200, description="Название события в календаре")
]
type CalendarComment = Annotated[
    str | None, Field(max_length=1000, description="Комментарий, например приказ")
]

PLANNED_WORKS = "planned_works"


class CalendarEventBase(BaseModel):
    """Общие проверки события: цель соответствует области действия, период не пустой."""

    starts_at: datetime = Field(description="Начало периода, со смещением часового пояса")
    ends_at: datetime = Field(description="Конец периода, не включается")

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("конец периода должен быть позже начала")
        return self


class CalendarEventCreate(CalendarEventBase):
    """Новое событие календаря; поставщик указывается только у плановых работ."""

    kind: CalendarKind
    scope: CalendarScope
    region_id: int | None = Field(
        default=None, description="Только и обязательно при scope=district"
    )
    school_id: int | None = Field(default=None, description="Только и обязательно при scope=school")
    provider_id: int | None = Field(
        default=None, description="Только при kind=planned_works: окно линий этого поставщика"
    )
    title: CalendarTitle
    comment: CalendarComment = None

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if (self.region_id is not None) != (self.scope == "district"):
            raise ValueError("region_id указывается только и обязательно при scope=district")
        if (self.school_id is not None) != (self.scope == "school"):
            raise ValueError("school_id указывается только и обязательно при scope=school")
        if self.provider_id is not None and self.kind != PLANNED_WORKS:
            raise ValueError("provider_id указывается только при kind=planned_works")
        return self


class CalendarEventUpdate(BaseModel):
    """Изменения события: период, название и комментарий; тип и цель не меняются."""

    starts_at: datetime | SkipJsonSchema[None] = None
    ends_at: datetime | SkipJsonSchema[None] = None
    title: CalendarTitle | SkipJsonSchema[None] = None
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at", "ends_at", "title", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("конец периода должен быть позже начала")
        return self


class CalendarEventDetail(CalendarEventBase):
    """Событие календаря с наименованиями его цели."""

    id: int
    kind: CalendarKind
    scope: CalendarScope
    region_id: int | None = Field(description="Только при scope=district")
    region_name: str | None
    school_id: int | None = Field(description="Только при scope=school")
    school_name: str | None
    provider_id: int | None = Field(description="Только при kind=planned_works")
    provider_name: str | None
    title: str
    comment: str | None


class CalendarEventDetailPage(Page[CalendarEventDetail]):
    """Страница событий календаря."""


class CalendarImportRequest(BaseModel):
    """Импорт календаря из таблицы: содержимое файла CSV одной строкой (T-70).

    Колонки: ``kind``, ``title``, ``start``, ``end`` обязательны, ``school_code``,
    ``region_code`` и ``comment`` — нет. Дата ``YYYY-MM-DD`` — целые местные сутки
    ``settings.timezone``, ``YYYY-MM-DDTHH:MM`` — момент этих суток.
    """

    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1_000_000,
            description="Содержимое файла CSV с заголовком kind,title,start,end",
        ),
    ]


class CalendarImportResult(BaseModel):
    """Итог импорта: сколько событий заведено и что не удалось прочитать."""

    created: int = Field(description="Сколько событий добавлено")
    errors: list[str] = Field(description="Строки файла, которые не удалось прочитать")
