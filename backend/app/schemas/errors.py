"""Error bodies of every endpoint: ``application/problem+json`` (RFC 9457, ADR-009)."""

from pydantic import BaseModel, Field


class Problem(BaseModel):
    """Error of any endpoint; clients branch on ``type``, ``detail`` is for a human."""

    type: str = Field(examples=["not_found"], description="Стабильный машинный код ошибки")
    title: str = Field(examples=["Не найдено"], description="Название ошибки для алерта")
    status: int = Field(examples=[404])
    detail: str | None = Field(default=None, description="Текст для человека")
    instance: str | None = Field(default=None, description="Путь запроса")


class FieldError(BaseModel):
    """One invalid field: dotted path from the request root, e.g. ``items[3].ping_ms``."""

    field: str = Field(examples=["items[3].ping_ms"])
    message: str = Field(examples=["Ожидается число"])


class ValidationProblem(Problem):
    """Request validation error (HTTP 422, ``type = validation_error``)."""

    type: str = Field(examples=["validation_error"], description="Стабильный машинный код ошибки")
    title: str = Field(examples=["Ошибка валидации"], description="Название ошибки для алерта")
    status: int = Field(examples=[422])
    errors: list[FieldError]
