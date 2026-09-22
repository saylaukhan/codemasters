"""Administration API (plan.md §10 «Админка»): every path starts with ``/api/admin``."""

from fastapi import APIRouter

from app.api.admin import (
    agent_releases,
    appeal_templates,
    audit_log,
    calendar,
    connection_types,
    contracts,
    digests,
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
    digests,
    agent_releases,
    audit_log,
    calendar,
):
    router.include_router(resource.router)
