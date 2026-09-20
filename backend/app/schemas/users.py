"""Requests and responses of user and role administration (plan.md §10 «Админка», ТЗ п. 16, п. 20).

The role fixes the one scope id a user has (ADR-008): Школа — ``school_id``, Район/город —
``region_id``, Провайдер — ``provider_id``, Область and Администратор — none. A user is blocked
with ``is_active = false`` and never deleted, so the audit log keeps his actions (ТЗ п. 16).
Passwords are write-only and stored as argon2 hashes (ТЗ п. 12). In a PATCH body an absent field
stays unchanged, and ``null`` for a field that cannot be empty is a 422.
"""

from typing import Annotated, Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.auth import PASSWORD_MAX_LENGTH, UserScope
from app.schemas.pagination import Page
from app.schemas.statuses import UserRole

# Shortest password an administrator may set; login still accepts any stored password.
PASSWORD_MIN_LENGTH = 8

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+$"

# Telegram chat id: digits, with a minus for a group; the bot token itself is never stored here.
TELEGRAM_CHAT_ID_MAX_LENGTH = 32

# Scope id required by each role (ADR-008); None — the whole oblast, no scope id at all.
ROLE_SCOPE_FIELD: dict[UserRole, str | None] = {
    "school": "school_id",
    "district": "region_id",
    "provider": "provider_id",
    "oblast": None,
    "admin": None,
}
SCOPE_ID_FIELDS = ("region_id", "provider_id", "school_id")


def check_role_scope(role: UserRole, body: BaseModel) -> None:
    """Raise ``ValueError`` unless ``body`` sets exactly the scope id of ``role``."""
    required = ROLE_SCOPE_FIELD[role]
    given = {name for name in SCOPE_ID_FIELDS if getattr(body, name) is not None}
    if required is None and given:
        raise ValueError(
            f"у роли {role} нет области видимости: {', '.join(sorted(given))} не нужны"
        )
    if required is not None and given != {required}:
        raise ValueError(f"для роли {role} укажите только {required}")


class UserCreate(BaseModel):
    """New panel user with a role, its scope and an initial password (T-38)."""

    email: str = Field(
        max_length=254, pattern=EMAIL_PATTERN, examples=["rayon@example.kz"], description="Логин"
    )
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    region_id: int | None = Field(
        default=None, description="Район или город (regions); только и обязательно для district"
    )
    provider_id: int | None = Field(default=None, description="Только и обязательно для provider")
    school_id: int | None = Field(default=None, description="Только и обязательно для school")
    password: SecretStr = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="Начальный пароль; хранится только хэшем",
    )
    telegram_chat_id: str | None = Field(
        default=None,
        max_length=TELEGRAM_CHAT_ID_MAX_LENGTH,
        examples=["123456789"],
        description="Чат пользователя с ботом уведомлений (T-42); пусто — канал ему не шлётся",
    )

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        check_role_scope(self.role, self)
        return self


class UserUpdate(BaseModel):
    """Changes of a user: data, role with scope, blocking, password reset.

    ``role`` and the scope ids travel together: with ``role`` the scope is replaced by the ids of
    this body (absent ids are cleared); a scope id without ``role`` is a 422.
    """

    email: Annotated[str, Field(max_length=254, pattern=EMAIL_PATTERN)] | SkipJsonSchema[None] = (
        None
    )
    full_name: Annotated[str, Field(min_length=1, max_length=255)] | SkipJsonSchema[None] = None
    role: UserRole | SkipJsonSchema[None] = None
    region_id: int | None = None
    provider_id: int | None = None
    school_id: int | None = None
    is_active: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="false — блокировка: вход и обновление токена запрещены, история остаётся",
    )
    password: (
        Annotated[SecretStr, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
        | SkipJsonSchema[None]
    ) = Field(default=None, description="Новый пароль: сброс администратором")
    telegram_chat_id: Annotated[str, Field(max_length=TELEGRAM_CHAT_ID_MAX_LENGTH)] | None = Field(
        default=None, description="Чат уведомлений (T-42); null — отключить канал пользователю"
    )

    @field_validator("email", "full_name", "role", "is_active", "password", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("поле не может быть null")
        return value

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        if self.role is not None:
            check_role_scope(self.role, self)
        elif self.model_fields_set & set(SCOPE_ID_FIELDS):
            raise ValueError("область видимости меняется только вместе с role")
        return self


class UserDetail(BaseModel):
    """Panel user in the administration list; the password is never returned."""

    id: int
    email: str
    full_name: str
    role: UserRole
    scope: UserScope
    scope_name: str | None = Field(
        examples=["Усть-Каменогорск"],
        description="Район или город, поставщик или школа области видимости; null — вся область",
    )
    is_active: bool = Field(description="false — учётная запись заблокирована")
    telegram_chat_id: str | None = Field(
        description="Чат уведомлений (T-42); null — Telegram этому пользователю не отправляется"
    )


class UserDetailPage(Page[UserDetail]):
    """Page of the users."""


class RoleListItem(BaseModel):
    """One of the five roles of ТЗ п. 16 with its permission codes (ADR-008)."""

    code: UserRole
    permissions: list[str] = Field(
        examples=[["schools:read", "incidents:read", "appeals:create"]],
        description="Коды прав роли для require(permission); матрица — T-20",
    )


class RoleListItemPage(Page[RoleListItem]):
    """Page of the roles."""
