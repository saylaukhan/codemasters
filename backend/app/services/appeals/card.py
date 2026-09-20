"""Sent appeals of the panel (T-48; ТЗ п. 17): the list, the card, the status and the PDF.

Every query runs in the session of the request, so RLS answers for the visibility: an appeal of
a line outside the user's scope simply does not exist here — 404 «не найдено», not 403 (ADR-008).
That is what makes the cabinet of the provider (T-44) a cabinet: he sees the appeals of his own
lines and moves their status, and an appeal of another provider is not there at all.

The statuses and the transitions are those of an incident (``incident_card.py``, ТЗ п. 19,
ADR-007): the same six, the same rule that only the district, the oblast and the administrator
close. Every change and every comment adds an ``appeal_events`` row, which is never rewritten.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.core.deps import PageParams
from app.core.errors import ApiError
from app.models import Appeal, AppealEvent, Incident, Provider, School, User
from app.schemas.appeals import (
    AppealDetail,
    AppealEventDetail,
    AppealListItem,
    AppealListItemPage,
    AppealUpdate,
)
from app.services.incident_card import CLOSING_ROLES, STATUS_LABELS, TRANSITIONS, invalid_transition
from app.services.references import page_of


def appeal_not_found() -> ApiError:
    return ApiError(404, "not_found", "Обращение не найдено")


@dataclass(frozen=True)
class AppealFilters:
    """Filters of the appeal list; ``period_to`` is not included."""

    statuses: Sequence[str] | None = None
    school_id: int | None = None
    provider_id: int | None = None
    incident_id: int | None = None
    q: str | None = None
    period_from: datetime | None = None
    period_to: datetime | None = None

    def conditions(self) -> list[ColumnElement[bool]]:
        found: list[ColumnElement[bool]] = []
        if self.statuses:
            found.append(Appeal.status.in_(self.statuses))
        if self.school_id is not None:
            found.append(Appeal.school_id == self.school_id)
        if self.provider_id is not None:
            found.append(Appeal.provider_id == self.provider_id)
        if self.incident_id is not None:
            found.append(Appeal.incident_id == self.incident_id)
        if self.q:
            found.append(Appeal.number.ilike(f"%{self.q}%"))
        if self.period_from is not None:
            found.append(Appeal.sent_at >= self.period_from)
        if self.period_to is not None:
            found.append(Appeal.sent_at < self.period_to)
        return found


def appeal_rows() -> Select[Any]:
    """Appeals with the names the list shows; the row is read anew, ``updated_at`` is the
    database's."""
    return (
        select(
            Appeal,
            School.school_code,
            School.full_name.label("school_name"),
            Provider.name.label("provider_name"),
            Incident.number.label("incident_number"),
        )
        .join(School, School.id == Appeal.school_id)
        .join(Provider, Provider.id == Appeal.provider_id)
        .outerjoin(Incident, Incident.id == Appeal.incident_id)
        .execution_options(populate_existing=True)
    )


def item_fields(row: Any) -> dict[str, Any]:
    appeal: Appeal = row.Appeal
    return {
        "id": appeal.id,
        "number": appeal.number,
        "status": appeal.status,
        "subject": appeal.subject,
        "incident_id": appeal.incident_id,
        "incident_number": row.incident_number,
        "school_id": appeal.school_id,
        "school_code": row.school_code,
        "school_name": row.school_name,
        "line_id": appeal.line_id,
        "provider_id": appeal.provider_id,
        "provider_name": row.provider_name,
        "sent_at": appeal.sent_at,
        "delivery_status": appeal.delivery_status,
    }


def event_detail(event: AppealEvent, author_user_name: str) -> AppealEventDetail:
    return AppealEventDetail.model_validate(
        {
            "id": event.id,
            "created_at": event.created_at,
            "author_user_id": event.author_user_id,
            "author_user_name": author_user_name,
            "status": event.to_status,
            "comment": event.comment,
        }
    )


async def appeal_list(
    session: AsyncSession, filters: AppealFilters, params: PageParams
) -> AppealListItemPage:
    query = (
        appeal_rows().where(*filters.conditions()).order_by(Appeal.sent_at.desc(), Appeal.id.desc())
    )
    rows, total = await page_of(session, query, params)
    return AppealListItemPage(
        items=[AppealListItem.model_validate(item_fields(row)) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def appeal_events(session: AsyncSession, appeal_id: int) -> list[AppealEventDetail]:
    rows = await session.execute(
        select(AppealEvent, User.full_name)
        .join(User, User.id == AppealEvent.author_user_id)
        .where(AppealEvent.appeal_id == appeal_id)
        .order_by(AppealEvent.created_at, AppealEvent.id)
    )
    return [event_detail(event, author) for event, author in rows]


async def appeal_detail(session: AsyncSession, appeal_id: int) -> AppealDetail:
    row = (await session.execute(appeal_rows().where(Appeal.id == appeal_id))).one_or_none()
    if row is None:
        raise appeal_not_found()
    appeal: Appeal = row.Appeal
    return AppealDetail.model_validate(
        {
            "id": appeal.id,
            "number": appeal.number,
            "status": appeal.status,
            "subject": appeal.subject,
            "text": appeal.text,
            "user_comment": appeal.user_comment,
            "context": appeal.context,
            "sent_at": appeal.sent_at,
            "recipient_email": appeal.recipient_email,
            "delivery_status": appeal.delivery_status,
            "events": await appeal_events(session, appeal_id),
        }
    )


async def locked_appeal(session: AsyncSession, appeal_id: int) -> Appeal:
    """The appeal for a change, locked against a parallel one; 404 outside the scope."""
    appeal = await session.scalar(
        select(Appeal)
        .where(Appeal.id == appeal_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if appeal is None:
        raise appeal_not_found()
    return appeal


async def update_appeal(
    session: AsyncSession, appeal_id: int, body: AppealUpdate, user: AuthUser, *, now: datetime
) -> AppealDetail:
    """Status change, comment or both; every one of them is a row of the history (ТЗ п. 17)."""
    appeal = await locked_appeal(session, appeal_id)
    if body.status is not None:
        source, target = appeal.status, body.status
        if target == "closed" and user.role not in CLOSING_ROLES:
            raise ApiError(
                403,
                "forbidden",
                "Закрыть обращение может пользователь района, области или администратор",
            )
        if target not in TRANSITIONS[source]:
            raise invalid_transition(
                f"Переход «{STATUS_LABELS[source]}» → «{STATUS_LABELS[target]}» не допускается"
            )
        appeal.status = target
        session.add(
            AppealEvent(
                appeal_id=appeal.id,
                kind="status_change",
                from_status=source,
                to_status=target,
                comment=body.comment,
                author_user_id=user.id,
                created_at=now,
            )
        )
    else:
        session.add(
            AppealEvent(
                appeal_id=appeal.id,
                kind="comment",
                comment=body.comment,
                author_user_id=user.id,
                created_at=now,
            )
        )
    await session.commit()
    return await appeal_detail(session, appeal_id)


async def appeal_pdf_file(session: AsyncSession, appeal_id: int) -> tuple[str, bytes]:
    """Number and the stored PDF of the appeal; 404 outside the scope or for an unknown id."""
    row = (
        await session.execute(select(Appeal.number, Appeal.pdf).where(Appeal.id == appeal_id))
    ).one_or_none()
    if row is None:
        raise appeal_not_found()
    return row.number, row.pdf
