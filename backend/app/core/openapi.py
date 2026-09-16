"""OpenAPI schema of the application: the single API contract (ADR-009).

FastAPI documents errors as ``application/json`` and adds its own ``HTTPValidationError``;
``ContractApp.openapi`` rewrites every error response to ``application/problem+json`` with the
``Problem`` / ``ValidationProblem`` schemas the error handlers actually return, and adds a
``default`` problem response to each operation.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.models import Schema
from fastapi.routing import APIRoute
from pydantic.json_schema import models_json_schema

from app.core.errors import PROBLEM_MEDIA_TYPE
from app.schemas.errors import Problem, ValidationProblem

REF_TEMPLATE = "#/components/schemas/{model}"
FASTAPI_ERROR_SCHEMAS = ("HTTPValidationError", "ValidationError")


def operation_id(route: APIRoute) -> str:
    """Operation id is the endpoint function name: ``list_schools`` in the generated client."""
    return route.name


class ContractApp(FastAPI):
    """FastAPI whose OpenAPI schema documents errors as problem+json."""

    _problem_schema: dict[str, Any] | None = None

    def openapi(self) -> dict[str, Any]:
        schema = super().openapi()
        # FastAPI regenerates the schema when routes change: rewrite each new schema once.
        if schema is not self._problem_schema:
            use_problem_json(schema)
            self._problem_schema = schema
        return schema


def problem_content(schema: dict[str, Any]) -> dict[str, Any]:
    return {PROBLEM_MEDIA_TYPE: {"schema": schema}}


def model_ref(model: type[Problem]) -> dict[str, str]:
    return {"$ref": REF_TEMPLATE.format(model=model.__name__)}


def use_problem_json(schema: dict[str, Any]) -> None:
    """Rewrite error responses and error schemas of ``schema`` in place."""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name in FASTAPI_ERROR_SCHEMAS:
        components.pop(name, None)
    _, error_schemas = models_json_schema(
        [(Problem, "validation"), (ValidationProblem, "validation")], ref_template=REF_TEMPLATE
    )
    for name, definition in error_schemas["$defs"].items():
        # Same normalisation FastAPI applies to its own components (drops "default": null).
        definition = jsonable_encoder(Schema(**definition), by_alias=True, exclude_none=True)
        if components.setdefault(name, definition) != definition:
            raise RuntimeError(f"схема {name} совпадает по имени со схемой ошибок problem+json")

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.setdefault("responses", {})
            for code, response in responses.items():
                if code == "422":
                    response["description"] = "Ошибка валидации запроса"
                    response["content"] = problem_content(model_ref(ValidationProblem))
                elif code[0] in "45":
                    # Keep a declared error model, only under the problem+json media type.
                    declared = response.get("content", {}).get("application/json", {})
                    error_schema = declared.get("schema", model_ref(Problem))
                    response["content"] = problem_content(error_schema)
            responses["default"] = {
                "description": "Ошибка (RFC 9457)",
                "content": problem_content(model_ref(Problem)),
            }
