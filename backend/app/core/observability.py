"""Observability of the server itself: Sentry for errors, Prometheus for metrics (T-54).

Watches the server, not the schools: the quality of the school channel is measured by the
agent and lives in ``measurements`` (ТЗ п. 3, plan.md §2). Here are the two signals that say
whether the server keeps up — an unhandled error and the rate and latency of requests and
Celery tasks.

Sentry starts only when ``SENTRY_DSN`` is set. An empty DSN is the normal local and offline
case: the application works exactly as before, nothing is sent anywhere. Reports carry no
personal data (``send_default_pii=False``): the system stores none (ТЗ п. 13), and an error
report must not become the first place where it appears.

Metrics are served by ``GET /metrics`` of the API and by a small HTTP server of the Celery
worker. Neither is published: Caddy proxies only ``/api/*`` outside (``deploy/Caddyfile``),
so both are reachable from inside the compose network only, where Prometheus scrapes them
(``deploy/prometheus/prometheus.yml``).

The path of a request is labelled with the route template (``/api/schools/{school_id}``), not
with the address that was called: one label per endpoint instead of one per school.

A prefork Celery worker counts in its children, so the children write to the directory of
``PROMETHEUS_MULTIPROC_DIR`` and the parent collects them (compose sets the variable for the
``worker`` service). Without the variable the registry is the ordinary process-wide one, which
is what the API and the tests use.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any

import sentry_sdk
from celery.signals import celeryd_init, task_failure, task_postrun, task_prerun
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
    start_http_server,
)
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Served by the API; excluded from its own metrics, so scraping does not inflate them.
METRICS_PATH = "/metrics"

# Label of a request that matched no route: 404 hunting must not create a label per address.
UNMATCHED = "unmatched"

# Seconds. The API answers in milliseconds, an export or a PDF in seconds (T-30, T-32).
HTTP_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Seconds. Detection of incidents and recomputation of the aggregates are minutes, not
# milliseconds (T-40, T-29), so the buckets run further out than the HTTP ones.
TASK_BUCKETS = (0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0)


def prepare_multiproc_dir() -> None:
    """Create the directory of the multiprocess counters and drop the files of the last run.

    Runs at import, before the first metric: ``prometheus_client`` decides there and then
    whether a counter lives in memory or in a file of that directory. The files left over
    belong to processes that no longer exist — keeping them would add the tasks of the
    previous start of the worker to the metrics of this one. Only ``*.db`` of this dedicated
    directory is removed.
    """
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return
    path = Path(multiproc_dir)
    path.mkdir(parents=True, exist_ok=True)
    for stale in path.glob("*.db"):
        stale.unlink(missing_ok=True)


prepare_multiproc_dir()

REQUESTS = Counter(
    "vko_http_requests_total",
    "Запросы к API по методу, маршруту и коду ответа",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "vko_http_request_duration_seconds",
    "Длительность обработки запроса к API",
    ["method", "path"],
    buckets=HTTP_BUCKETS,
)
TASKS = Counter(
    "vko_celery_tasks_total",
    "Задачи Celery по имени и исходу: success или failure",
    ["task", "state"],
)
TASK_DURATION = Histogram(
    "vko_celery_task_duration_seconds",
    "Длительность выполнения задачи Celery",
    ["task"],
    buckets=TASK_BUCKETS,
)


def init_sentry(component: str) -> bool:
    """Start Sentry for ``component`` (``api`` or ``worker``); return whether it started.

    An empty ``SENTRY_DSN`` leaves the process without Sentry and is not an error: the
    installation may have no place to send reports to (plan.md §13).
    """
    settings = get_settings()
    if not settings.sentry_dsn:
        logger.info("Sentry выключен: SENTRY_DSN не задан")
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=f"vko-monitor-backend@{__version__}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # ТЗ п. 13: система не собирает персональных данных — и отчёт об ошибке тоже.
        send_default_pii=False,
    )
    sentry_sdk.set_tag("component", component)
    logger.info("Sentry включён", extra={"environment": settings.sentry_environment})
    return True


def metrics_registry() -> CollectorRegistry:
    """Return the registry to render: the multiprocess one when the directory is set."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return REGISTRY
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=multiproc_dir)
    return registry


def render_metrics() -> tuple[bytes, str]:
    """Return the body and the content type of the Prometheus exposition."""
    return generate_latest(metrics_registry()), CONTENT_TYPE_LATEST


def route_template(scope: Scope) -> str:
    """Return the route template of the request, or ``unmatched``.

    Starlette fills ``scope["route"]`` only inside the router, which runs after this
    middleware, so the routes are matched here the same way the router matches them. A path
    that matches but under another method (405) still names its route: the endpoint exists.
    """
    partial = ""
    for route in scope["app"].routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return str(getattr(route, "path_format", None) or route.path)
        if match == Match.PARTIAL and not partial:
            partial = str(getattr(route, "path_format", None) or route.path)
    return partial or UNMATCHED


class MetricsMiddleware:
    """Counts every HTTP request and how long it took."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == METRICS_PATH:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = route_template(scope)
        started = time.perf_counter()
        # An exception on the way out never reaches ``http.response.start``; the request still
        # ended for the client, and 500 is what the error handler answers (ADR-009).
        status = 500

        async def record_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        finally:
            REQUEST_DURATION.labels(method, path).observe(time.perf_counter() - started)
            REQUESTS.labels(method, path, str(status)).inc()


def install_worker_metrics() -> None:
    """Connect the Celery signals that count tasks and serve the metrics of the worker.

    Called from ``app/workers/celery_app.py`` at import, so both the worker and beat get it.
    """
    started: dict[str, float] = {}

    @task_prerun.connect(weak=False)
    def _started(task_id: str | None = None, **_: Any) -> None:
        if task_id:
            started[task_id] = time.perf_counter()

    @task_postrun.connect(weak=False)
    def _finished(task_id: str | None = None, task: Any = None, state: str = "", **_: Any) -> None:
        name = getattr(task, "name", "unknown")
        began = started.pop(task_id, None) if task_id else None
        if began is not None:
            TASK_DURATION.labels(name).observe(time.perf_counter() - began)
        # ``task_failure`` counts the failures, so here only what did not fail is counted:
        # otherwise a failed task would be counted twice.
        if state != "FAILURE":
            TASKS.labels(name, "success").inc()

    @task_failure.connect(weak=False)
    def _failed(sender: Any = None, **_: Any) -> None:
        TASKS.labels(getattr(sender, "name", "unknown"), "failure").inc()

    @celeryd_init.connect(weak=False)
    def _serve(**_: Any) -> None:
        init_sentry("worker")
        port = get_settings().worker_metrics_port
        # Runs in the parent process of a prefork worker; the children write their counters
        # into PROMETHEUS_MULTIPROC_DIR and the registry here reads them back.
        start_http_server(port, registry=metrics_registry())
        logger.info("метрики воркера отдаются на порту %s", port)
