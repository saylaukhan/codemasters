"""HTTP API routers by domain (plan.md §10); every path starts with ``/api`` (ADR-009)."""

from fastapi import APIRouter

from app.api import agent

API_PREFIX = "/api"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(agent.router)
