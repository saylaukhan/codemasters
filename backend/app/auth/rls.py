"""Row-level security of panel requests (ADR-008): the role ``vko_panel`` and ``app.user_scope``.

The application connects as the owner of the tables, and the owner — a superuser in the compose
image — is not subject to RLS. ``require`` therefore switches the transaction of a panel
request to ``vko_panel`` (created by the migration of T-20) and puts the scope of the user into
``app.user_scope``; the policies of that migration read it. His id goes into ``app.user_id``
next to it, for the tables that belong to a person rather than to a district
(``notifications``, T-42). All three are ``SET LOCAL``: they end with the transaction and never
reach another request through the connection pool. A commit inside an endpoint starts a new
transaction, so the listener below repeats them at the start of every transaction of a scoped
session.

Agent requests, the login and the audit middleware run as the owner, outside any scope.
"""

from sqlalchemy import Connection, event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from app.schemas.statuses import UserRole

PANEL_ROLE = "vko_panel"
SCOPE_SETTING = "app.user_scope"
# Id of the panel user: notifications belong to a person, not to his district (T-42).
USER_SETTING = "app.user_id"
# Key of ``Session.info`` that marks a scoped session; holds ``(scope, user_id)``.
SCOPE_KEY = "rls_scope"

# Scope of Область and Администратор: the whole oblast.
WHOLE_OBLAST = "all"


def scope_value(
    role: UserRole, *, region_id: int | None, provider_id: int | None, school_id: int | None
) -> str:
    """Value of ``app.user_scope`` for a user: ``all``, ``region:<id>``, ``provider:<id>``,
    ``school:<id>``; an empty string — a role without its scope id — sees nothing."""
    if role in ("oblast", "admin"):
        return WHOLE_OBLAST
    if role == "district":
        kind, scope_id = "region", region_id
    elif role == "provider":
        kind, scope_id = "provider", provider_id
    else:
        kind, scope_id = "school", school_id
    return "" if scope_id is None else f"{kind}:{scope_id}"


def _enter_scope(connection: Connection, scope: str, user_id: int | None) -> None:
    connection.execute(text(f"SET LOCAL ROLE {PANEL_ROLE}"))
    connection.execute(select(func.set_config(SCOPE_SETTING, scope, True)))
    user = "" if user_id is None else str(user_id)
    connection.execute(select(func.set_config(USER_SETTING, user, True)))


@event.listens_for(Session, "after_begin")
def _scope_new_transaction(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    scoped = session.info.get(SCOPE_KEY)
    if scoped is not None:
        _enter_scope(connection, *scoped)


async def apply_scope(session: AsyncSession, scope: str, user_id: int | None = None) -> None:
    """Run the rest of the session's work as ``vko_panel`` limited to ``scope``.

    Without ``user_id`` — a background build that only borrows the scope of a user (T-33) — the
    session reads nothing that belongs to a person, such as his notifications.
    """
    session.info[SCOPE_KEY] = (scope, user_id)
    connection = await session.connection()
    await connection.run_sync(_enter_scope, scope, user_id)


async def clear_scope(session: AsyncSession) -> None:
    """Return the session to the owner: the request is over, the session may be reused."""
    if session.info.pop(SCOPE_KEY, None) is None or not session.in_transaction():
        return
    try:
        await session.execute(text("SET LOCAL ROLE NONE"))
        await session.execute(select(func.set_config(SCOPE_SETTING, "", True)))
        await session.execute(select(func.set_config(USER_SETTING, "", True)))
    except DBAPIError:
        # The transaction has already failed: its rollback ends all three SET LOCAL anyway.
        return
