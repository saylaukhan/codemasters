"""HTTP API routers by domain (plan.md §10); every path starts with ``/api`` (ADR-009)."""

from fastapi import APIRouter

from app.api import agent, auth, dashboard, devices, schools
from app.api import map as school_map

API_PREFIX = "/api"

api_router = APIRouter(prefix=API_PREFIX)
for domain in (agent, auth, dashboard, school_map, schools, devices):
    api_router.include_router(domain.router)
