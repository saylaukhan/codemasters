"""Audit log (ТЗ п. 12, п. 16; ADR-008): sign-ins, changing actions, rejected agent requests.

``AuditMiddleware`` (installed in ``app/main.py``) writes one record after a request is
answered: a successful POST / PATCH / PUT / DELETE of a panel user, and a rejected request of
an agent (``transfer_error``). What was touched is read from the path: ``PATCH
/api/schools/5/lines/7`` is an ``update`` of ``line`` 7, a POST that creates a row takes the id
from the response. Agent and sign-in requests are told apart by the module of the endpoint:
FastAPI keeps nested routers unflattened, so the route object carries neither the ``/api``
prefix nor the tags of the router it is included in. An endpoint that knows more — a block, a
password reset, the changed fields — says so with ``describe_action``. Sign-ins are written by
the login endpoint itself (``record_login``): it knows the typed e-mail and why it refused.

The record is written in a session of its own after the response has been sent, so a failed
action leaves no record and a slow log does not slow the answer; a request the rate limit
refused before routing writes its record itself (``app/core/ratelimit.py``, T-51). Request and
response bodies never get into the log: only the ``id`` and the problem ``type`` are taken from
the answer.
"""

import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.deps import AuthUser
from app.core.db import get_session_factory
from app.models import AuditLog
from app.schemas.audit import AuditAction, AuditEntityType

logger = logging.getLogger(__name__)

CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Endpoints of the agent (ADR-005) and of the panel sign-in (logged by the login itself).
AGENT_MODULE = "app.api.agent"
AUTH_MODULE = "app.api.auth"
# Longest decimal that fits into bigint ids.
MAX_ID_DIGITS = 18

# Path segment of a resource → the entity type of its records.
ENTITY_BY_SEGMENT: dict[str, AuditEntityType] = {
    "schools": "school",
    "lines": "line",
    "points": "monitoring_point",
    "contacts": "school_contact",
    "devices": "device",
    "enrollment-codes": "enrollment_code",
    "incidents": "incident",
    "appeals": "appeal",
    "exports": "export",
    "users": "user",
    "providers": "provider",
    "regions": "region",
    "connection-types": "connection_type",
    "thresholds": "threshold_profile",
    "schedules": "schedule",
    "settings": "setting",
    "incident-rules": "incident_rule",
    "appeal-templates": "appeal_template",
    "agent-releases": "agent_release",
    # The import of a contract registry is an ``import`` of lines (T-87).
    "contracts": "line",
}
# Action segments after the id of an entity.
ACTION_BY_SEGMENT: dict[str, AuditAction] = {
    "block": "block",
    "unblock": "unblock",
    "status": "status_change",
}
# POST requests that change nothing: an AI draft of an appeal is only shown to its author, a
# preview of an import reports what the file would change and writes nothing (T-87).
NOT_CHANGING_SEGMENTS = frozenset({"draft", "preview"})

# Rejections of an agent request that are transfer errors (ТЗ п. 12). 409 is not one: a
# duplicate tells the agent the record is already stored (ADR-006).
TRANSFER_ERROR_STATUSES = frozenset({400, 401, 403, 413, 415, 422})

# Larger answers are not read for their id: a created row answers with a small object.
MAX_CAPTURED_BODY = 64 * 1024

type AuditSessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass
class AuditEntry:
    """Fields of one ``audit_log`` row."""

    action: AuditAction
    entity_type: AuditEntityType
    entity_id: int | None = None
    user_id: int | None = None
    user_email: str | None = None
    changes: dict[str, Any] | None = None
    error_type: str | None = None
    ip: IPv4Address | IPv6Address | None = None

    def row(self) -> AuditLog:
        return AuditLog(
            action=self.action,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            user_id=self.user_id,
            user_email=self.user_email,
            changes=self.changes,
            error_type=self.error_type,
            ip=self.ip,
        )


@dataclass
class ActionDescription:
    """What an endpoint adds to the record the middleware derives from its path."""

    action: AuditAction | None = None
    entity_id: int | None = None
    changes: dict[str, Any] | None = field(default=None)


def describe_action(
    request: Request,
    *,
    action: AuditAction | None = None,
    entity_id: int | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    """Refine the audit record of this request: ``block`` instead of ``update``, the changed
    fields as ``{field: {"old": ..., "new": ...}}`` (never passwords, tokens or codes)."""
    request.state.audit = ActionDescription(action=action, entity_id=entity_id, changes=changes)


def client_ip(scope: Scope) -> IPv4Address | IPv6Address | None:
    client = scope.get("client")
    if not client:
        return None
    try:
        return ip_address(client[0])
    except ValueError:
        return None


def record_login(
    session: AsyncSession,
    request: Request,
    *,
    email: str,
    user_id: int | None,
    error_type: str | None = None,
) -> None:
    """Add a ``login_success`` / ``login_failure`` record to the session (no commit)."""
    entry = AuditEntry(
        action="login_failure" if error_type else "login_success",
        entity_type="user",
        entity_id=user_id,
        user_id=user_id,
        user_email=email,
        error_type=error_type,
        ip=client_ip(request.scope),
    )
    session.add(entry.row())


def record_self_change(
    session: AsyncSession,
    request: Request,
    *,
    user: AuthUser,
    changes: dict[str, Any],
) -> None:
    """Add an ``update`` record of a user changing his own account (no commit).

    The middleware skips the sign-in module (``AUTH_MODULE``), so the endpoints of a profile
    write their record themselves, the way ``record_login`` does.
    """
    entry = AuditEntry(
        action="update",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        user_email=user.email,
        changes=changes,
        ip=client_ip(request.scope),
    )
    session.add(entry.row())


def response_json(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def path_entity(path: str, method: str) -> tuple[AuditAction, AuditEntityType, int | None] | None:
    """Action, entity type and id of a changing panel request, from its path."""
    entity_type: AuditEntityType | None = None
    entity_id: int | None = None
    action: AuditAction | None = None
    for segment in path.split("/"):
        if segment in NOT_CHANGING_SEGMENTS:
            return None
        if segment.isdecimal() and len(segment) <= MAX_ID_DIGITS:
            entity_id = int(segment)
        elif segment in ENTITY_BY_SEGMENT:
            entity_type, entity_id = ENTITY_BY_SEGMENT[segment], None
        elif segment in ACTION_BY_SEGMENT:
            action = ACTION_BY_SEGMENT[segment]
    if entity_type is None:
        return None
    if action is None:
        if entity_type == "export":
            action = "export"
        elif method == "POST" and entity_id is None:
            action = "create"
        else:
            action = "update"
    return action, entity_type, entity_id


def audit_entry(scope: Scope, status: int, body: bytes) -> AuditEntry | None:
    """Record of an answered request, or ``None`` when the request is not audited."""
    module = getattr(scope.get("endpoint"), "__module__", None)
    if module is None or module == AUTH_MODULE:
        return None
    state = scope.get("state", {})
    if module == AGENT_MODULE:
        if status not in TRANSFER_ERROR_STATUSES:
            return None
        return AuditEntry(
            action="transfer_error",
            entity_type="device",
            entity_id=state.get("device_id"),
            error_type=response_json(body).get("type"),
            ip=client_ip(scope),
        )
    user = state.get("user")
    if not isinstance(user, AuthUser) or not 200 <= status < 300:
        return None
    derived = path_entity(scope["path"], scope["method"])
    if derived is None:
        return None
    action, entity_type, entity_id = derived
    if entity_id is None and action in ("create", "export"):
        created_id = response_json(body).get("id")
        entity_id = created_id if isinstance(created_id, int) else None
    entry = AuditEntry(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user.id,
        user_email=user.email,
        ip=client_ip(scope),
    )
    described = state.get("audit")
    if isinstance(described, ActionDescription):
        entry.action = described.action or entry.action
        entry.entity_id = described.entity_id or entry.entity_id
        entry.changes = described.changes
    return entry


class AuditMiddleware:
    """ASGI middleware writing the audit record of a changing request after it is answered.

    Records go through ``app.state.audit_sessions`` when it is set (tests put their own
    session there), otherwise through a session of the application's engine.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in CHANGING_METHODS:
            await self.app(scope, receive, send)
            return
        scope.setdefault("state", {})
        status = 0
        body = bytearray()

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and len(body) < MAX_CAPTURED_BODY:
                body.extend(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        entry = audit_entry(scope, status, bytes(body))
        if entry is not None:
            await self.write(scope, entry)

    async def write(self, scope: Scope, entry: AuditEntry) -> None:
        await write_entry(scope["app"], entry)


async def write_entry(application: Starlette, entry: AuditEntry) -> None:
    """Write one record in a session of its own (the rate limit of T-51 writes its own too).

    Records go through ``app.state.audit_sessions`` when it is set (tests put their own session
    there), otherwise through a session of the application's engine.
    """
    sessions: AuditSessions = getattr(application.state, "audit_sessions", None) or (
        get_session_factory()
    )
    try:
        async with sessions() as session:
            session.add(entry.row())
            await session.commit()
    except SQLAlchemyError:
        # The answer is already sent: a lost record is logged, not turned into a 500.
        logger.exception("audit record not written: %s %s", entry.action, entry.entity_type)
