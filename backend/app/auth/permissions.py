"""Role → permission matrix (ADR-008 «Открыто», plan.md §9, ТЗ п. 16).

Every panel endpoint declares one of these codes with ``require("<permission>")``; the panel
gets the same list from ``GET /api/auth/me`` only to hide what a role cannot use. Which rows a
permitted request sees is decided separately, by the scope and RLS (``app/auth/rls.py``).

Rule of the matrix: Школа — view and appeals; Район/город — plus analytics, incidents,
appeals; Провайдер — view of its lines and the status of incidents and appeals; Область —
everything except technical administration: thresholds, schedules, incident rules,
references, settings; Администратор — the same plus users, devices, agent releases and logs.
"""

from app.schemas.statuses import UserRole

# Read access; the scope decides which schools, lines and devices are visible.
VIEW = frozenset(
    {
        "dashboard:read",
        "map:read",
        "schools:read",
        "devices:read",
        "analytics:read",
        "incidents:read",
        "appeals:read",
        "exports:create",
        # His own bell (T-42): every role has one, and it shows only what his scope let him see.
        "notifications:read",
    }
)

# Settings of the monitoring, changed without code (ТЗ п. 11, п. 20).
MONITORING_SETUP = frozenset(
    {
        "schools:write",
        "references:manage",
        "thresholds:manage",
        "schedules:manage",
        "incident_rules:manage",
        "settings:manage",
    }
)

# Technical administration: accounts, agents on the computers, logs (ТЗ п. 16).
ADMINISTRATION = frozenset(
    {"users:manage", "devices:manage", "agent_releases:manage", "audit:read"}
)

# Phone of a responsible person of a school (ТЗ п. 15): the provider gets the contacts without it.
CONTACT_PHONE = frozenset({"contacts:phone"})

ROLE_PERMISSIONS: dict[UserRole, frozenset[str]] = {
    "school": VIEW | CONTACT_PHONE | {"appeals:create"},
    "district": VIEW
    | CONTACT_PHONE
    | {"appeals:create", "appeals:update", "incidents:create", "incidents:update"},
    "provider": VIEW | {"appeals:update", "incidents:update"},
    "oblast": VIEW
    | CONTACT_PHONE
    | MONITORING_SETUP
    | {"appeals:create", "appeals:update", "incidents:create", "incidents:update"},
    "admin": VIEW
    | CONTACT_PHONE
    | MONITORING_SETUP
    | ADMINISTRATION
    | {"appeals:create", "appeals:update", "incidents:create", "incidents:update"},
}

PERMISSIONS = frozenset().union(*ROLE_PERMISSIONS.values())
