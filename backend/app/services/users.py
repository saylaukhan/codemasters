"""User administration (T-38, ТЗ п. 16, п. 20; ADR-008): list, create, change, block.

A user is never deleted: blocking sets ``is_active = false``, login and refresh refuse him and
his records in ``audit_log`` stay. Passwords are stored as argon2 hashes only (ТЗ п. 12). A
block or a password reset raises ``token_version``, so every token issued before dies at once.
The role and its scope travel together (``check_role_scope``): the one row of ``user_scopes``
is replaced, or deleted when the new role sees the whole oblast.

An administrator cannot block himself or take the role away from himself: the panel would be
left without anyone to undo it. Only the Администратор calls these endpoints; his scope is the
whole oblast, so RLS hides nothing here.
"""

from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthUser
from app.auth.permissions import ROLE_PERMISSIONS
from app.core.deps import PageParams
from app.core.errors import ApiError
from app.core.security import hash_password
from app.models import Provider, Region, School, User
from app.models import UserScope as ScopeRow
from app.schemas.audit import AuditAction
from app.schemas.auth import UserScope
from app.schemas.statuses import UserRole
from app.schemas.users import (
    ROLE_SCOPE_FIELD,
    SCOPE_ID_FIELDS,
    RoleListItem,
    RoleListItemPage,
    UserCreate,
    UserDetail,
    UserDetailPage,
    UserUpdate,
)
from app.services.references import Changes, apply_changes, invalid_field, is_taken, matching

# Order of the roles in the list: from the narrowest scope to the whole oblast (ТЗ п. 16).
ROLE_ORDER: tuple[UserRole, ...] = ("school", "district", "oblast", "provider", "admin")

SCOPE_MODELS: dict[str, type[Region] | type[Provider] | type[School]] = {
    "region_id": Region,
    "provider_id": Provider,
    "school_id": School,
}
SCOPE_NOT_FOUND = {
    "region_id": "Район или город не найден",
    "provider_id": "Поставщик не найден",
    "school_id": "Школа не найдена",
}


def email_taken() -> ApiError:
    return ApiError(409, "email_taken", "E-mail уже занят другим пользователем")


def user_not_found() -> ApiError:
    return ApiError(404, "not_found", "Пользователь не найден")


def normalize_email(email: str) -> str:
    # Login compares the e-mail lower-case (app/api/auth.py).
    return email.strip().lower()


def detail_query() -> Select[Any]:
    """Users with their scope row, the district name and the name of the scope."""
    return (
        select(
            User,
            ScopeRow,
            Region.name.label("region_name"),
            func.coalesce(Region.name, Provider.name, School.full_name).label("scope_name"),
        )
        .outerjoin(ScopeRow, ScopeRow.user_id == User.id)
        .outerjoin(Region, Region.id == ScopeRow.region_id)
        .outerjoin(Provider, Provider.id == ScopeRow.provider_id)
        .outerjoin(School, School.id == ScopeRow.school_id)
    )


def user_detail(
    user: User, scope: ScopeRow | None, region_name: str | None, scope_name: str | None
) -> UserDetail:
    return UserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=cast(UserRole, user.role),
        scope=UserScope(
            region_id=scope.region_id if scope else None,
            region_name=region_name,
            provider_id=scope.provider_id if scope else None,
            school_id=scope.school_id if scope else None,
        ),
        scope_name=scope_name,
        is_active=user.is_active,
    )


async def load_detail(session: AsyncSession, user_id: int) -> UserDetail:
    row = (await session.execute(detail_query().where(User.id == user_id))).one()
    return user_detail(*row)


async def user_list(
    session: AsyncSession,
    params: PageParams,
    *,
    roles: list[UserRole] | None,
    is_active: bool | None,
    region_id: int | None,
    provider_id: int | None,
    school_id: int | None,
    q: str | None,
) -> UserDetailPage:
    filters = matching(q, User.full_name, User.email)
    if roles:
        filters.append(User.role.in_(roles))
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    for column, value in (
        (ScopeRow.region_id, region_id),
        (ScopeRow.provider_id, provider_id),
        (ScopeRow.school_id, school_id),
    ):
        if value is not None:
            filters.append(column == value)
    query = detail_query().where(*filters).order_by(User.full_name, User.id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (await session.execute(query.limit(params.page_size).offset(params.offset))).all()
    return UserDetailPage(
        items=[user_detail(*row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def check_scope_ids(session: AsyncSession, body: UserCreate | UserUpdate) -> None:
    """422 on the field of a scope id that names no row."""
    for field, model in SCOPE_MODELS.items():
        value = getattr(body, field)
        if (
            value is not None
            and await session.scalar(select(model.id).where(model.id == value)) is None
        ):
            raise invalid_field(field, SCOPE_NOT_FOUND[field])


def scope_ids(role: UserRole, body: UserCreate | UserUpdate) -> dict[str, int | None]:
    """Scope ids of the row for ``role``; all three are None for Область and Администратор."""
    field = ROLE_SCOPE_FIELD[role]
    return {name: getattr(body, name) if name == field else None for name in SCOPE_ID_FIELDS}


async def create_user(session: AsyncSession, body: UserCreate) -> UserDetail:
    email = normalize_email(body.email)
    if await is_taken(session, User.email, email, None):
        raise email_taken()
    await check_scope_ids(session, body)
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(body.password.get_secret_value()),
    )
    session.add(user)
    await session.flush()
    ids = scope_ids(body.role, body)
    if any(value is not None for value in ids.values()):
        session.add(ScopeRow(user_id=user.id, **ids))
    await session.commit()
    return await load_detail(session, user.id)


async def replace_scope(
    session: AsyncSession, user: User, role: UserRole, body: UserUpdate
) -> Changes:
    """Put the scope of ``role`` from ``body`` in place of the old one; changed ids."""
    row = await session.scalar(select(ScopeRow).where(ScopeRow.user_id == user.id))
    ids = scope_ids(role, body)
    old = {name: getattr(row, name) if row else None for name in SCOPE_ID_FIELDS}
    if ROLE_SCOPE_FIELD[role] is None:
        if row is not None:
            await session.delete(row)
    elif row is None:
        session.add(ScopeRow(user_id=user.id, **ids))
    else:
        for name, value in ids.items():
            setattr(row, name, value)
    return {name: {"old": old[name], "new": ids[name]} for name in ids if old[name] != ids[name]}


def check_not_self(actor: AuthUser, user: User, body: UserUpdate) -> None:
    """An administrator keeps his own access: no self-block, no other role for himself."""
    if actor.id != user.id:
        return
    if body.is_active is False:
        raise invalid_field("is_active", "Нельзя заблокировать собственную учётную запись")
    if body.role is not None and body.role != user.role:
        raise invalid_field("role", "Нельзя сменить роль собственной учётной записи")


async def update_user(
    session: AsyncSession, user_id: int, body: UserUpdate, actor: AuthUser
) -> tuple[UserDetail, AuditAction | None, Changes]:
    """Apply the PATCH; the audit action (block, unblock, password reset) and changed fields."""
    user = await session.get(User, user_id)
    if user is None:
        raise user_not_found()
    check_not_self(actor, user, body)
    updates: dict[str, Any] = {}
    if body.email is not None:
        email = normalize_email(body.email)
        if await is_taken(session, User.email, email, user.id):
            raise email_taken()
        updates["email"] = email
    if body.full_name is not None:
        updates["full_name"] = body.full_name.strip()
    if body.role is not None:
        await check_scope_ids(session, body)
        updates["role"] = body.role
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    changes = apply_changes(user, updates)
    if body.role is not None:
        changes.update(await replace_scope(session, user, body.role, body))

    action: AuditAction | None = None
    if body.password is not None:
        user.password_hash = hash_password(body.password.get_secret_value())
        action = "password_reset"
    if "is_active" in changes:
        action = "unblock" if user.is_active else "block"
    if body.password is not None or changes.get("is_active", {}).get("new") is False:
        # Sessions opened with the old password or before the block end now.
        user.token_version += 1
    await session.commit()
    return await load_detail(session, user.id), action, changes


def role_list(params: PageParams) -> RoleListItemPage:
    roles = [
        RoleListItem(code=role, permissions=sorted(ROLE_PERMISSIONS[role])) for role in ROLE_ORDER
    ]
    return RoleListItemPage(
        items=roles[params.offset : params.offset + params.page_size],
        total=len(roles),
        page=params.page,
        page_size=params.page_size,
    )
