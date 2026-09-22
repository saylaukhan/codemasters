"""Every error leaves the API as ``application/problem+json`` (RFC 9457, ADR-009).

``register_error_handlers`` (called in ``app/main.py``) replaces the FastAPI defaults
(``{"detail": ...}``) for request validation, HTTP exceptions and unhandled exceptions.
Endpoints raise ``ApiError`` with a stable ``type`` code; ``not_implemented`` marks contract
stubs until their task lands. HTTP middleware runs outside these handlers: it answers with
``problem_response(...)`` itself instead of raising (an ``ApiError`` raised there still keeps
its status and headers, but Starlette logs it as an unhandled error).
"""

import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import FieldError, Problem, ValidationProblem

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Stable ``type`` codes and Russian titles by status. ``http.HTTPStatus`` names are not used:
# Python 3.13 renames some of them (413, 422), which would change the contract.
STATUS_PROBLEMS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Некорректный запрос"),
    401: ("unauthorized", "Требуется авторизация"),
    403: ("forbidden", "Доступ запрещён"),
    404: ("not_found", "Не найдено"),
    405: ("method_not_allowed", "Метод не поддерживается"),
    406: ("not_acceptable", "Формат ответа не поддерживается"),
    409: ("conflict", "Конфликт с текущим состоянием"),
    413: ("payload_too_large", "Слишком большой запрос"),
    415: ("unsupported_media_type", "Неподдерживаемый формат запроса"),
    422: ("validation_error", "Ошибка валидации"),
    429: ("too_many_requests", "Слишком много запросов"),
    500: ("internal_error", "Внутренняя ошибка сервера"),
    501: ("not_implemented", "Не реализовано"),
    503: ("service_unavailable", "Сервис недоступен"),
}

# Russian ``errors[].message`` by pydantic error type; placeholders come from the error context.
# Types missing here keep the pydantic message.
VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "Обязательное поле",
    "extra_forbidden": "Неизвестное поле",
    "json_invalid": "Некорректный JSON",
    "value_error": "{error}",
    "literal_error": "Допустимые значения: {expected}",
    "enum": "Допустимые значения: {expected}",
    "string_type": "Ожидается строка",
    "string_too_short": "Минимальная длина — {min_length}",
    "string_too_long": "Максимальная длина — {max_length}",
    "string_pattern_mismatch": "Значение не соответствует формату",
    "base64_decode": "Ожидается содержимое в base64",
    "int_type": "Ожидается целое число",
    "int_parsing": "Ожидается целое число",
    "int_from_float": "Ожидается целое число",
    "float_type": "Ожидается число",
    "float_parsing": "Ожидается число",
    "bool_type": "Ожидается true или false",
    "bool_parsing": "Ожидается true или false",
    "greater_than": "Значение должно быть больше {gt}",
    "greater_than_equal": "Значение должно быть не меньше {ge}",
    "less_than": "Значение должно быть меньше {lt}",
    "less_than_equal": "Значение должно быть не больше {le}",
    "list_type": "Ожидается список",
    "too_short": "Минимальная длина — {min_length}",
    "too_long": "Максимальная длина — {max_length}",
    "model_type": "Ожидается объект",
    "model_attributes_type": "Ожидается объект",
    "dict_type": "Ожидается объект",
    "uuid_type": "Ожидается UUID",
    "uuid_parsing": "Ожидается UUID",
    "datetime_type": "Ожидается дата и время RFC 3339",
    "datetime_parsing": "Ожидается дата и время RFC 3339",
    "datetime_from_date_parsing": "Ожидается дата и время RFC 3339",
    "timezone_aware": "Время должно быть со смещением часового пояса",
    "date_type": "Ожидается дата ГГГГ-ММ-ДД",
    "date_parsing": "Ожидается дата ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "Ожидается дата ГГГГ-ММ-ДД",
    "time_type": "Ожидается время ЧЧ:ММ",
    "time_parsing": "Ожидается время ЧЧ:ММ",
    "ip_any_address": "Ожидается IPv4- или IPv6-адрес",
    "ip_any_network": "Ожидается сеть в формате CIDR, например 203.0.113.0/24",
}

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Error with a stable machine code ``type`` and a human-readable ``detail``."""

    def __init__(
        self,
        status: int,
        type_: str,
        detail: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail or type_)
        self.status = status
        self.type = type_
        self.detail = detail
        self.headers = headers


def not_implemented(task: str) -> ApiError:
    """Error of a contract stub: the endpoint is described in OpenAPI but lands in ``task``."""
    return ApiError(
        HTTPStatus.NOT_IMPLEMENTED,
        "not_implemented",
        f"Эндпоинт описан в контракте, реализация — {task}",
    )


class ProblemResponse(JSONResponse):
    media_type = PROBLEM_MEDIA_TYPE


def status_problem(status: int, type_: str | None = None, detail: str | None = None) -> Problem:
    """Problem for an HTTP status; ``type`` defaults to the code of ``STATUS_PROBLEMS``."""
    default_type, title = STATUS_PROBLEMS.get(status, (f"http_{status}", "Ошибка"))
    return Problem(type=type_ or default_type, title=title, status=status, detail=detail)


def problem_response(
    request: Request,
    problem: Problem,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Serialize ``problem`` with ``instance`` = request path; ``None`` members are omitted.

    Statuses that must not have a body (204, 304, 1xx) get an empty response with ``headers``.
    """
    if not is_body_allowed_for_status_code(problem.status):
        return Response(status_code=problem.status, headers=headers)
    problem.instance = request.url.path
    return ProblemResponse(
        problem.model_dump(mode="json", exclude_none=True),
        status_code=problem.status,
        headers=headers,
    )


def without_null_branches(errors: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Drop the noise of ``X | SkipJsonSchema[None]`` PATCH fields.

    For such a union pydantic reports one error per branch: ``("full_name", "none")`` of type
    ``none_required`` and ``("full_name", "constrained-str")`` with the real problem. The null
    branch is removed and its position tells where the branch tag sits in the other errors.
    """
    branches = {
        tuple(error["loc"][:-1])
        for error in errors
        if error["type"] == "none_required" and error["loc"][-1] == "none"
    }
    cleaned: list[Mapping[str, Any]] = []
    for error in errors:
        location = tuple(error["loc"])
        if location[:-1] in branches and error["type"] == "none_required":
            continue
        for prefix in branches:
            if len(location) > len(prefix) and location[: len(prefix)] == prefix:
                location = location[: len(prefix)] + location[len(prefix) + 1 :]
                break
        cleaned.append({**error, "loc": location})
    return cleaned


def field_path(error: Mapping[str, Any]) -> str:
    """Error location as a field path: ``("body", "items", 3, "ping_ms")`` → ``items[3].ping_ms``.

    The source (``body``, ``query``, ...) is dropped unless it is the whole location, and so are
    pydantic tags of union members (``lax-or-strict[...]``), which are not field names. A JSON
    syntax error points at the source: its location holds a character offset, not a field.
    """
    location = error["loc"]
    if error["type"] == "json_invalid":
        return str(location[0])
    path = ""
    for part in location[1:] or location:
        if isinstance(part, int):
            path += f"[{part}]"
        elif part.isidentifier():
            path += f".{part}"
    return path.lstrip(".")


def field_message(error: Mapping[str, Any]) -> str:
    """Russian message for a pydantic error; unknown types keep the pydantic text."""
    template = VALIDATION_MESSAGES.get(error["type"])
    if template is None:
        return str(error["msg"])
    try:
        return template.format(**error.get("ctx", {}))
    except (KeyError, IndexError):
        return str(error["msg"])


async def handle_api_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiError)
    problem = status_problem(exc.status, exc.type, exc.detail)
    return problem_response(request, problem, exc.headers)


async def handle_http_exception(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    # Starlette fills an empty detail with the English status phrase: the title covers it.
    phrase = HTTPStatus(exc.status_code).phrase if exc.status_code in HTTPStatus else None
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail != phrase else None
    problem = status_problem(exc.status_code, detail=detail)
    return problem_response(request, problem, exc.headers)


async def handle_validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    errors: list[FieldError] = []
    for error in without_null_branches(exc.errors()):
        field_error = FieldError(field=field_path(error), message=field_message(error))
        if field_error not in errors:
            errors.append(field_error)
    problem = ValidationProblem(
        type="validation_error",
        title=STATUS_PROBLEMS[422][1],
        status=422,
        detail="Запрос не прошёл проверку: см. errors",
        errors=errors,
    )
    return problem_response(request, problem)


async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
    # Errors raised in HTTP middleware reach only this handler: keep their status and headers.
    if isinstance(exc, ApiError):
        return await handle_api_error(request, exc)
    if isinstance(exc, StarletteHTTPException):
        return await handle_http_exception(request, exc)
    # The traceback goes to the log only: the response must not leak internals.
    logger.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return problem_response(request, status_problem(500, detail="Внутренняя ошибка сервера"))


def register_error_handlers(application: FastAPI) -> None:
    """Install the problem+json handlers on ``application``."""
    application.add_exception_handler(ApiError, handle_api_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_exception)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(Exception, handle_unexpected_error)
