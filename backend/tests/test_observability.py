"""Observability: metrics of the API and Sentry that stays off without a DSN (T-54).

No database: the application is built directly, the way ``test_smoke.py`` does it.
"""

import sentry_sdk
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from app.core.config import get_settings
from app.core.observability import UNMATCHED, init_sentry
from app.main import create_app


def samples(body: str, name: str) -> dict[tuple[str, ...], float]:
    """Return ``{label values: value}`` of the metric ``name`` in the exposition ``body``."""
    found: dict[tuple[str, ...], float] = {}
    for family in text_string_to_metric_families(body):
        for sample in family.samples:
            if sample.name == name:
                found[tuple(sorted(sample.labels.items()))] = sample.value
    return found


def test_metrics_endpoint_serves_prometheus_exposition() -> None:
    client = TestClient(create_app())

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "vko_http_requests_total" in response.text


def test_request_is_counted_under_its_route_template() -> None:
    client = TestClient(create_app())

    before = samples(client.get("/metrics").text, "vko_http_requests_total")
    client.get("/api/health")
    after = samples(client.get("/metrics").text, "vko_http_requests_total")

    health = (("method", "GET"), ("path", "/api/health"), ("status", "200"))
    assert after[health] == before.get(health, 0.0) + 1


def test_an_endpoint_of_an_included_router_answers_and_is_counted() -> None:
    """Regression: the routers of ``app/api`` are attached with ``include_router``.

    Matching the top level of ``app.routes`` finds the object that stands for such a router,
    which carries no path at all — reading a template off it turned every ``/api/*`` request
    into 500. The template is read after the router has run instead.
    """
    client = TestClient(create_app())

    response = client.get("/api/schools")

    # No token: 401 is the answer of the endpoint, and any 5xx means the metrics broke routing.
    assert response.status_code == 401, response.text
    counted = samples(client.get("/metrics").text, "vko_http_requests_total")
    paths = {dict(labels)["path"] for labels in counted}
    assert "/api/schools" in paths
    assert not any(p == UNMATCHED for p in paths if p == "/api/schools")


def test_a_path_parameter_is_replaced_by_its_name() -> None:
    """One label per endpoint, not one per school: the id must not reach the label."""
    client = TestClient(create_app())

    client.get("/api/schools/7/devices")

    counted = samples(client.get("/metrics").text, "vko_http_requests_total")
    paths = {dict(labels)["path"] for labels in counted}
    assert not any("/7/" in p for p in paths), paths
    assert any(p.startswith("/api/schools/{") for p in paths), paths


def test_unknown_path_does_not_create_a_label_of_its_own() -> None:
    client = TestClient(create_app())

    client.get("/api/schools/404-not-a-route/whatever")
    body = client.get("/metrics").text

    counted = samples(body, "vko_http_requests_total")
    assert any(dict(labels)["path"] == UNMATCHED for labels in counted)
    assert not any("404-not-a-route" in dict(labels)["path"] for labels in counted)


def test_scraping_metrics_does_not_count_itself() -> None:
    client = TestClient(create_app())

    client.get("/metrics")
    body = client.get("/metrics").text

    counted = samples(body, "vko_http_requests_total")
    assert not any(dict(labels)["path"] == "/metrics" for labels in counted)


def test_application_works_without_sentry_dsn() -> None:
    """An empty DSN is the normal case: Sentry stays off and the API answers as before."""
    assert get_settings().sentry_dsn == ""

    started = init_sentry("api")

    assert started is False
    assert sentry_sdk.get_client().is_active() is False
    assert TestClient(create_app()).get("/api/health").status_code == 200
