"""Incidents of the panel (T-41; ТЗ п. 19; plan.md §7; ADR-007): list, card, manual creation,
status changes, comments and the auto-close.

Every query of a request runs in its session, so RLS limits it to the user's scope: an incident
of a line outside it is «не найден», not «запрещён», and a line outside it is unknown to a manual
incident (ADR-008). A status moves only along ``TRANSITIONS``; every transition and comment adds
an ``incident_events`` row, which is never rewritten. Durations are whole seconds (ADR-014):
``restored_at − started_at`` and, for the provider, ``restored_at − sent_to_provider_at``.
«Устранён» turns into «Закрыт» after ``AUTO_CLOSE_AFTER`` by beat, as the owner of the tables.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Incident, IncidentEvent, Line, Provider, School, User
from app.models.incident import OPEN_FOR_DETECTION
from app.schemas.incidents import (
    IncidentCreate,
    IncidentDetail,
    IncidentEventDetail,
    IncidentListItem,
    IncidentListItemPage,
    IncidentStatusChange,
    IncidentUpdate,
)
from app.services.incidents import LOCK_KEY, incident_number
from app.services.references import Changes, apply_changes, invalid_field, page_of
from app.services.school_card import ensure_school
from app.services.settings import system_settings

# Allowed transitions (T-41): forward in the order of ТЗ п. 19 with the intermediate statuses
# optional, «Закрыт» only from «Устранён»; back only to «В работе» — from «Ожидает информации»,
# and from «Устранён» when the problem came back before the closing. Nothing leaves «Закрыт».
TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"sent_to_provider", "in_progress", "awaiting_info", "resolved"}),
    "sent_to_provider": frozenset({"in_progress", "awaiting_info", "resolved"}),
    "in_progress": frozenset({"awaiting_info", "resolved"}),
    "awaiting_info": frozenset({"in_progress", "resolved"}),
    "resolved": frozenset({"in_progress", "closed"}),
    "closed": frozenset(),
}

# Labels of ``INCIDENT_STATUS_LABELS`` in ``web/src/lib/labels.ts``, for the error messages.
STATUS_LABELS = {
    "new": "Новый",
    "sent_to_provider": "Передан поставщику",
    "in_progress": "В работе",
    "awaiting_info": "Ожидает информации",
    "resolved": "Устранён",
    "closed": "Закрыт",
}

# The provider reports a fix; closing it is for the district and the oblast (ADR-007).
CLOSING_ROLES = frozenset({"district", "oblast", "admin"})

# «Устранён» for this long without the problem coming back becomes «Закрыт» (ТЗ п. 19).
AUTO_CLOSE_AFTER = timedelta(hours=24)
AUTO_CLOSE_COMMENT = "Закрыт автоматически: 24 ч в статусе «Устранён»"

INVALID_TRANSITION = "invalid_status_transition"


def incident_not_found() -> ApiError:
    return ApiError(404, "not_found", "Инцидент не найден")


def invalid_transition(detail: str) -> ApiError:
    return ApiError(409, INVALID_TRANSITION, detail)


def seconds_between(start: datetime | None, end: datetime | None) -> int | None:
    """Whole seconds from ``start`` to ``end``; None without one of them or when negative."""
    if start is None or end is None or end < start:
        return None
    return int((end - start).total_seconds())


@dataclass(frozen=True)
class IncidentFilters:
    """Filters of the incident list; ``period_to`` is not included."""

    statuses: Sequence[str] | None = None
    school_id: int | None = None
    region_id: int | None = None
    provider_id: int | None = None
    line_id: int | None = None
    q: str | None = None
    period_from: datetime | None = None
    period_to: datetime | None = None

    def conditions(self) -> list[ColumnElement[bool]]:
        found: list[ColumnElement[bool]] = []
        if self.statuses:
            found.append(Incident.status.in_(self.statuses))
        if self.school_id is not None:
            found.append(Incident.school_id == self.school_id)
        if self.region_id is not None:
            found.append(School.region_id == self.region_id)
        if self.provider_id is not None:
            found.append(Incident.provider_id == self.provider_id)
        if self.line_id is not None:
            found.append(Incident.line_id == self.line_id)
        if self.q:
            found.append(Incident.number.ilike(f"%{self.q}%"))
        if self.period_from is not None:
            found.append(Incident.started_at >= self.period_from)
        if self.period_to is not None:
            found.append(Incident.started_at < self.period_to)
        return found


def incident_rows() -> Select[Any]:
    """Incidents with the names the list shows. The rows are read anew even when the session
    already holds them: ``updated_at`` of a changed incident is set by the database."""
    return (
        select(
            Incident,
            School.school_code,
            School.full_name.label("school_name"),
            Line.status.label("line_status"),
            Provider.name.label("provider_name"),
            User.full_name.label("responsible_user_name"),
        )
        .join(School, School.id == Incident.school_id)
        .join(Line, Line.id == Incident.line_id)
        .join(Provider, Provider.id == Incident.provider_id)
        .outerjoin(User, User.id == Incident.responsible_user_id)
        .execution_options(populate_existing=True)
    )


def item_fields(row: Any) -> dict[str, Any]:
    incident: Incident = row.Incident
    return {
        "id": incident.id,
        "number": incident.number,
        "status": incident.status,
        "school_id": incident.school_id,
        "school_code": row.school_code,
        "school_name": row.school_name,
        "line_id": incident.line_id,
        "line_status": row.line_status,
        "provider_id": incident.provider_id,
        "provider_name": row.provider_name,
        "basis_metrics": incident.basis_metrics,
        "started_at": incident.started_at,
        "duration_s": seconds_between(incident.started_at, incident.restored_at),
        "responsible_user_id": incident.responsible_user_id,
        "responsible_user_name": row.responsible_user_name,
    }


def event_detail(event: IncidentEvent, author_user_name: str | None) -> IncidentEventDetail:
    return IncidentEventDetail.model_validate(
        {
            "id": event.id,
            "kind": event.kind,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "comment": event.comment,
            "author_user_id": event.author_user_id,
            "author_user_name": author_user_name,
            "created_at": event.created_at,
        }
    )


async def incident_list(
    session: AsyncSession, filters: IncidentFilters, params: PageParams
) -> IncidentListItemPage:
    query = (
        incident_rows()
        .where(*filters.conditions())
        .order_by(Incident.started_at.desc(), Incident.id.desc())
    )
    rows, total = await page_of(session, query, params)
    return IncidentListItemPage(
        items=[IncidentListItem.model_validate(item_fields(row)) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def school_incidents(
    session: AsyncSession, school_id: int, params: PageParams
) -> IncidentListItemPage:
    """Incidents of a school card; 404 for a school outside the scope."""
    await ensure_school(session, school_id)
    return await incident_list(session, IncidentFilters(school_id=school_id), params)


async def incident_events(session: AsyncSession, incident_id: int) -> list[IncidentEventDetail]:
    rows = await session.execute(
        select(IncidentEvent, User.full_name)
        .outerjoin(User, User.id == IncidentEvent.author_user_id)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.created_at, IncidentEvent.id)
    )
    return [event_detail(event, author) for event, author in rows]


async def incident_detail(session: AsyncSession, incident_id: int) -> IncidentDetail:
    row = (await session.execute(incident_rows().where(Incident.id == incident_id))).one_or_none()
    if row is None:
        raise incident_not_found()
    incident: Incident = row.Incident
    return IncidentDetail.model_validate(
        item_fields(row)
        | {
            "rule_id": incident.rule_id,
            "description": incident.description,
            "last_violation_at": incident.last_violation_at,
            "sent_to_provider_at": incident.sent_to_provider_at,
            "restored_at": incident.restored_at,
            "closed_at": incident.closed_at,
            "provider_reaction_s": seconds_between(
                incident.sent_to_provider_at, incident.restored_at
            ),
            "created_at": incident.created_at,
            "updated_at": incident.updated_at,
            "events": await incident_events(session, incident_id),
        }
    )


async def locked_incident(session: AsyncSession, incident_id: int) -> Incident:
    """The incident for a change, locked against a parallel one; 404 outside the scope."""
    incident = await session.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if incident is None:
        raise incident_not_found()
    return incident


async def check_responsible(session: AsyncSession, user_id: int | None) -> None:
    """422 on ``responsible_user_id`` unless the user exists and is not blocked."""
    if user_id is None:
        return
    if not await session.scalar(select(User.is_active).where(User.id == user_id)):
        raise invalid_field("responsible_user_id", "Пользователь не найден или заблокирован")


async def create_incident(
    session: AsyncSession, body: IncidentCreate, user: AuthUser, *, now: datetime
) -> int:
    """Manual incident from the school card: ``new``, no rule, the school and the provider of
    the line; the metrics are named without values, a person saw no measurement (ТЗ п. 19)."""
    line = await session.scalar(select(Line).where(Line.id == body.line_id))
    if line is None:
        raise invalid_field("line_id", "Линия не найдена")
    if body.started_at is not None and body.started_at > now:
        raise invalid_field("started_at", "Начало проблемы не может быть в будущем")
    await check_responsible(session, body.responsible_user_id)
    settings = await system_settings(session)
    incident = Incident(
        number=await incident_number(session, settings, now),
        status="new",
        line_id=line.id,
        school_id=line.school_id,
        provider_id=line.provider_id,
        basis_metrics=[
            {"metric": metric, "value": None, "threshold": None} for metric in body.metrics
        ],
        description=body.description,
        started_at=body.started_at or now,
        responsible_user_id=body.responsible_user_id,
    )
    session.add(incident)
    await session.flush()
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            kind="created",
            to_status="new",
            author_user_id=user.id,
            created_at=now,
        )
    )
    await session.commit()
    return incident.id


async def update_incident(session: AsyncSession, incident_id: int, body: IncidentUpdate) -> Changes:
    """Responsible person and description; the changed fields for the audit record."""
    incident = await locked_incident(session, incident_id)
    updates = body.model_dump(exclude_unset=True)
    await check_responsible(session, updates.get("responsible_user_id"))
    changes = apply_changes(incident, updates)
    await session.commit()
    return changes


async def reopen(session: AsyncSession, incident: Incident) -> None:
    """«Устранён» → «В работе»: the problem came back, the incident is not restored any more.

    A rule incident is then open for the detection again (T-40), which may meanwhile have opened
    a newer one for the same line and rule: only one of them may be open. The lock of the
    detection keeps it from opening one between the check and the commit.
    """
    if incident.rule_id is not None:
        await session.execute(select(func.pg_advisory_xact_lock(LOCK_KEY, incident.line_id)))
        other = await session.scalar(
            select(Incident.number).where(
                Incident.line_id == incident.line_id,
                Incident.rule_id == incident.rule_id,
                Incident.id != incident.id,
                text(OPEN_FOR_DETECTION),
            )
        )
        if other is not None:
            raise invalid_transition(
                f"Проблема уже отслеживается инцидентом {other}: вернуть этот в работу нельзя"
            )
    incident.restored_at = None


async def change_status(
    session: AsyncSession,
    incident_id: int,
    body: IncidentStatusChange,
    user: AuthUser,
    *,
    now: datetime,
) -> Changes:
    """Move the incident along ``TRANSITIONS`` and write the event; the changed status for
    the audit record. 403 when a role that may not close tries to, 409 for any other move."""
    incident = await locked_incident(session, incident_id)
    source, target = incident.status, body.status
    if target == "closed" and user.role not in CLOSING_ROLES:
        raise ApiError(
            403,
            "forbidden",
            "Закрыть инцидент может пользователь района, области или администратор",
        )
    if target not in TRANSITIONS[source]:
        raise invalid_transition(
            f"Переход «{STATUS_LABELS[source]}» → «{STATUS_LABELS[target]}» не допускается"
        )
    if source == "resolved" and target == "in_progress":
        await reopen(session, incident)
    elif target == "sent_to_provider":
        incident.sent_to_provider_at = now
    elif target == "resolved" and incident.restored_at is None:
        incident.restored_at = now
    elif target == "closed":
        incident.closed_at = now
    incident.status = target
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            kind="status_change",
            from_status=source,
            to_status=target,
            comment=body.comment,
            author_user_id=user.id,
            created_at=now,
        )
    )
    await session.commit()
    return {"status": {"old": source, "new": target}}


async def add_comment(
    session: AsyncSession, incident_id: int, comment: str, user: AuthUser, *, now: datetime
) -> IncidentEventDetail:
    """A comment in the history; the status stays."""
    await locked_incident(session, incident_id)
    event = IncidentEvent(
        incident_id=incident_id,
        kind="comment",
        comment=comment,
        author_user_id=user.id,
        created_at=now,
    )
    session.add(event)
    await session.commit()
    return event_detail(event, user.full_name)


async def close_resolved(session: AsyncSession, *, now: datetime) -> list[int]:
    """Close the incidents «Устранён» for ``AUTO_CLOSE_AFTER``; the caller commits.

    Runs from beat as the owner of the tables, outside any scope. The time counts from the latest
    transition to ``resolved``: a problem that came back and was fixed again waits anew. An
    incident without that event (loaded, not moved by a person) counts from ``updated_at``. The
    event has no author: the system closed it.
    """
    resolved_at = (
        select(func.max(IncidentEvent.created_at))
        .where(
            IncidentEvent.incident_id == Incident.id,
            IncidentEvent.kind == "status_change",
            IncidentEvent.to_status == "resolved",
        )
        .scalar_subquery()
    )
    incidents = (
        await session.scalars(
            select(Incident)
            .where(
                Incident.status == "resolved",
                func.coalesce(resolved_at, Incident.updated_at) <= now - AUTO_CLOSE_AFTER,
            )
            .order_by(Incident.id)
            .with_for_update(of=Incident, skip_locked=True)
        )
    ).all()
    for incident in incidents:
        incident.status = "closed"
        incident.closed_at = now
        session.add(
            IncidentEvent(
                incident_id=incident.id,
                kind="status_change",
                from_status="resolved",
                to_status="closed",
                comment=AUTO_CLOSE_COMMENT,
                created_at=now,
            )
        )
    await session.flush()
    return [incident.id for incident in incidents]
