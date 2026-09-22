"""Administration API (plan.md §10 «Админка»): every path starts with ``/api/admin``."""

from fastapi import APIRouter

from app.api.admin import (
    agent_releases,
    appeal_templates,
    audit_log,
    connection_types,
    contracts,
    incident_rules,
    providers,
    regions,
    roles,
    schedules,
    settings,
    thresholds,
    users,
)

router = APIRouter(prefix="/admin")
for resource in (
    users,
    roles,
    providers,
    regions,
    connection_types,
    thresholds,
    schedules,
    settings,
    incident_rules,
    appeal_templates,
    contracts,
    agent_releases,
    audit_log,
):
    router.include_router(resource.router)
