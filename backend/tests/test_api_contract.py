"""API contract (ADR-009): problem+json errors, the list envelope, OpenAPI in sync with the code.

Error handling is exercised through test-only routes without authentication, so these tests
do not depend on the contract stubs that T-14…T-50 replace with real endpoints.
"""

import json
import re
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import Depends, HTTPException, Request, Response
from fastapi.testclient import TestClient
from httpx import Response as HttpxResponse
from pydantic import BaseModel, ValidationError

from app.core.deps import PageParams, page_params
from app.core.errors import PROBLEM_MEDIA_TYPE, ApiError
from app.main import create_app
from app.schemas.agent import MeasurementBatchRequest, OutageCreate
from app.schemas.pagination import Page

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "reference" / "openapi.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


class Item(BaseModel):
    id: int


class ItemPage(Page[Item]):
    pass


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Application with test-only routes: a list, a request body and failing endpoints."""
    application = create_app()

    @application.get("/api/test/items")
    async def list_test_items(params: Annotated[PageParams, Depends(page_params)]) -> ItemPage:
        items = [Item(id=number) for number in range(1, 26)]
        return ItemPage(
            items=items[params.offset : params.offset + params.page_size],
            total=len(items),
            page=params.page,
            page_size=params.page_size,
        )

    @application.post("/api/test/batch", status_code=204)
    async def accept_test_batch(body: MeasurementBatchRequest) -> None:
        return None

    @application.get("/api/test/not-modified")
    async def not_modified() -> None:
        raise HTTPException(304, headers={"ETag": '"v1"'})

    @application.get("/api/test/dict-detail")
    async def dict_detail() -> None:
        raise HTTPException(400, detail={"internal": "structure"})

    @application.get("/api/test/crash")
    async def crash() -> None:
        raise RuntimeError("database password is hunter2")

    @application.middleware("http")
    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/api/test/limited":
            raise ApiError(429, "too_many_requests", "Повторите позже", {"Retry-After": "60"})
        return await call_next(request)

    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client


def assert_problem(response: HttpxResponse, status: int, type_: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body: dict[str, Any] = response.json()
    assert body["type"] == type_
    assert body["status"] == status
    assert body["title"]
    assert body["instance"] == response.request.url.path
    assert "detail" not in body or isinstance(body["detail"], str)
    return body


def measurement(**fields: Any) -> dict[str, Any]:
    valid = {
        "measurement_uuid": "0b5e2c1e-8f0a-4c55-9d7e-3f1c2a4b5d6e",
        "measured_at": "2026-09-17T08:41:00+05:00",
        "connection_status": "online",
        "agent_version": "0.1.0",
    }
    return valid | fields


def test_validation_error_is_problem_json_with_field_errors(client: TestClient) -> None:
    response = client.post(
        "/api/test/batch",
        json={
            "items": [
                measurement(),
                measurement(measurement_uuid="not-a-uuid", download_mbps="fast"),
                measurement(external_ip="999.1.1.1", measured_at="2026-09-17T08:41:00"),
            ]
        },
    )

    body = assert_problem(response, 422, "validation_error")
    assert body["title"] == "Ошибка валидации"
    assert body["errors"] == [
        {"field": "items[1].measurement_uuid", "message": "Ожидается UUID"},
        {"field": "items[1].download_mbps", "message": "Ожидается число"},
        {
            "field": "items[2].measured_at",
            "message": "Время должно быть со смещением часового пояса",
        },
        {"field": "items[2].external_ip", "message": "Ожидается IPv4- или IPv6-адрес"},
    ]


def test_query_and_json_syntax_errors_name_the_field(client: TestClient) -> None:
    query = client.get("/api/test/items", params={"page_size": 0})
    syntax = client.post(
        "/api/test/batch", content=b"{broken", headers={"content-type": "application/json"}
    )

    assert assert_problem(query, 422, "validation_error")["errors"] == [
        {"field": "page_size", "message": "Значение должно быть не меньше 1"}
    ]
    assert assert_problem(syntax, 422, "validation_error")["errors"] == [
        {"field": "body", "message": "Некорректный JSON"}
    ]


def test_list_is_items_total_page_page_size(client: TestClient) -> None:
    response = client.get("/api/test/items", params={"page": 2, "page_size": 10})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert (body["total"], body["page"], body["page_size"]) == (25, 2, 10)
    assert [item["id"] for item in body["items"]] == list(range(11, 21))
    page_schema = client.get("/api/openapi.json").json()["components"]["schemas"]["ItemPage"]
    assert set(page_schema["required"]) == {"items", "total", "page", "page_size"}


def test_http_errors_are_problem_json(client: TestClient) -> None:
    not_found = assert_problem(client.get("/api/no-such-route"), 404, "not_found")
    not_allowed = client.delete("/api/health")
    dict_detail = assert_problem(client.get("/api/test/dict-detail"), 400, "bad_request")

    assert not_found["title"] == "Не найдено"
    assert assert_problem(not_allowed, 405, "method_not_allowed")["instance"] == "/api/health"
    assert not_allowed.headers["allow"] == "GET"
    assert "detail" not in dict_detail


def test_status_without_body_keeps_headers_and_sends_no_problem(client: TestClient) -> None:
    response = client.get("/api/test/not-modified")

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == '"v1"'


def test_error_raised_in_middleware_keeps_status_and_headers(client: TestClient) -> None:
    response = client.get("/api/test/limited")

    assert_problem(response, 429, "too_many_requests")
    assert response.headers["retry-after"] == "60"


def test_unexpected_error_is_problem_json_without_internals(client: TestClient) -> None:
    response = client.get("/api/test/crash")

    assert_problem(response, 500, "internal_error")
    assert "hunter2" not in response.text


def test_contract_stub_answers_not_implemented(client: TestClient) -> None:
    response = client.post(
        "/api/devices/register",
        json={"enrollment_code": "VKO-7F3K-92QD", "device_uid": "pc-1", "agent_version": "0.1.0"},
    )

    body = assert_problem(response, 501, "not_implemented")
    assert "T-14" in body["detail"]


def test_outage_cannot_end_before_it_starts() -> None:
    started_at = datetime(2026, 9, 17, 10, tzinfo=UTC)

    with pytest.raises(ValidationError, match="ended_at"):
        OutageCreate(started_at=started_at, ended_at=started_at - timedelta(minutes=1))


def operations(schema: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield f"{method.upper()} {path}", operation


def test_openapi_documents_errors_as_problem_json() -> None:
    schema = create_app().openapi()
    component_names = schema["components"]["schemas"]

    assert "HTTPValidationError" not in component_names
    # Generic models must be named subclasses: ``Page_School_`` is not a panel type name.
    assert all(re.fullmatch(r"[A-Z][A-Za-z0-9]*", name) for name in component_names)
    for name, operation in operations(schema):
        responses = operation["responses"]
        assert PROBLEM_MEDIA_TYPE in responses["default"]["content"], name
        for code, response in responses.items():
            if code[0] in "45":
                assert set(response["content"]) == {PROBLEM_MEDIA_TYPE}, f"{name} {code}"


def test_operation_ids_are_unique_function_names() -> None:
    operation_ids = [
        operation["operationId"] for _, operation in operations(create_app().openapi())
    ]

    assert len(operation_ids) == len(set(operation_ids))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", operation_id) for operation_id in operation_ids)


def property_names(schema: Any, components: dict[str, Any]) -> set[str]:
    """Every property name reachable from ``schema``: ``$ref``, combinators, items, maps."""
    if not isinstance(schema, dict):
        return set()
    if "$ref" in schema:
        return property_names(components[schema["$ref"].rsplit("/", 1)[1]], components)
    names = set(schema.get("properties", {}))
    children = [*schema.get("properties", {}).values(), *schema.get("prefixItems", [])]
    for key in ("anyOf", "oneOf", "allOf"):
        children += schema.get(key, [])
    children += [schema.get("items"), schema.get("additionalProperties")]
    for child in children:
        names |= property_names(child, components)
    return names


def test_agent_requests_carry_no_school_line_or_status() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]
    forbidden = {"school_id", "school_code", "line_id", "quality_status"}

    checked = []
    for name, operation in operations(schema):
        if "agent" in operation.get("tags", []) and "requestBody" in operation:
            body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
            assert not property_names(body_schema, components) & forbidden, name
            checked.append(operation["operationId"])

    assert set(checked) >= {"register_device", "create_measurement", "create_measurement_batch"}


def test_agent_endpoints_declare_the_device_token() -> None:
    schema = create_app().openapi()

    for name, operation in operations(schema):
        if "agent" in operation.get("tags", []) and operation["operationId"] != "register_device":
            assert operation.get("security") == [{"DeviceToken": []}], name


# Endpoints of plan.md §10 already in the contract; T-03 parts 2 and 3 extend the set.
PLAN_ENDPOINTS = {
    "POST /api/devices/register",
    "POST /api/devices/heartbeat",
    "GET /api/agent/config",
    "GET /api/agent/whoami",
    "POST /api/measurements",
    "POST /api/measurements/batch",
    "POST /api/outages",
    "GET /api/agent/releases/latest",
    "POST /api/auth/login",
    "POST /api/auth/refresh",
    "POST /api/auth/logout",
    "GET /api/auth/me",
    "GET /api/dashboard/summary",
    "GET /api/map/schools",
}


def test_contract_has_every_endpoint_of_the_plan() -> None:
    documented = {name for name, _ in operations(create_app().openapi())}

    assert PLAN_ENDPOINTS - documented == set()


def test_panel_endpoints_declare_the_bearer_token() -> None:
    for name, operation in operations(create_app().openapi()):
        if set(operation.get("tags", [])) & {"agent", "auth", "health"}:
            continue
        assert operation.get("security") == [{"BearerAuth": []}], name


def test_personal_data_only_in_contacts_and_users() -> None:
    """ТЗ п. 15, ADR-003: phones and e-mails of people live only in contacts and user accounts."""
    components = create_app().openapi()["components"]["schemas"]
    allowed = ("SchoolContact", "CurrentUser", "Login", "User")

    for name, component in components.items():
        if set(component.get("properties", {})) & {"phone", "email", "position"}:
            assert name.startswith(allowed), name


def test_openapi_file_matches_the_code() -> None:
    generated = json.loads(json.dumps(create_app().openapi()))

    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert committed == generated, "контракт устарел: выполните make openapi и закоммитьте"


def test_swagger_ui_opens(client: TestClient) -> None:
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
