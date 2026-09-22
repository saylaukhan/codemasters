"""HTTP API routers by domain (plan.md §10); every path starts with ``/api`` (ADR-009)."""

from fastapi import APIRouter

from app.api import (
    admin,
    agent,
    analytics,
    appeals,
    auth,
    dashboard,
    devices,
    exports,
    incidents,
    notifications,
    providers,
    rollout,
    schools,
)
from app.api import map as school_map

API_PREFIX = "/api"

api_router = APIRouter(prefix=API_PREFIX)
for domain in (
    agent,
    auth,
    dashboard,
    school_map,
    schools,
    devices,
    analytics,
    incidents,
    notifications,
    appeals,
    providers,
    exports,
    rollout,
    admin,
):
    api_router.include_router(domain.router)
