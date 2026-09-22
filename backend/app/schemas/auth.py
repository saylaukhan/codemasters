"""Requests and responses of panel authentication (plan.md §10, ADR-008, ADR-009).

Passwords are checked against argon2 hashes (ТЗ п. 12). Personal data here is limited to the
user's own e-mail and full name.
"""

from pydantic import BaseModel, Field, SecretStr

from app.schemas.statuses import UserRole

# Upper bound of a password: argon2 hashes whatever it gets, a cap keeps login cheap.
PASSWORD_MAX_LENGTH = 128
# Shortest password the API takes, wherever one is set: an administrator sets the first one
# (``app/schemas/users.py``), the owner of a reset link sets his own.
PASSWORD_MIN_LENGTH = 8
# Token of a reset link: the id of its row, a dot and 32 random bytes in url-safe base64.
RESET_TOKEN_MAX_LENGTH = 200


class LoginRequest(BaseModel):
    """Panel sign-in; the password never shows up in logs or reprs (``SecretStr``)."""

    email: str = Field(min_length=1, max_length=254, examples=["admin@example.kz"])
    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class AccessTokenResponse(BaseModel):
    """Access JWT for ``Authorization: Bearer``."""

    access_token: str
    expires_in_s: int = Field(ge=1, examples=[900], description="Срок жизни access-токена")


class UserScope(BaseModel):
    """Visibility scope of a user (ADR-008); the profile menu shows the district (DESIGN.md §3.5).

    Школа — ``school_id``, Район/город — ``region_id``, Провайдер — ``provider_id``;
    Область and Администратор see the whole oblast, so every field is null.
    """

    region_id: int | None
    region_name: str | None
    provider_id: int | None
    school_id: int | None


class CurrentUser(BaseModel):
    """User of the access token: role, scope and permissions to shape the panel.

    Permissions only hide what the panel cannot use: the API checks them again (ТЗ п. 16).
    """

    id: int
    email: str = Field(examples=["rayon@example.kz"])
    full_name: str
    role: UserRole
    scope: UserScope
    permissions: list[str] = Field(
        examples=[["schools:read", "incidents:read", "appeals:create"]],
        description="Коды прав роли для require(permission); матрица — T-20",
    )


class PasswordResetRequest(BaseModel):
    """Request of a reset link; the answer is the same for every address (T-65)."""

    email: str = Field(
        min_length=1,
        max_length=254,
        examples=["admin@example.kz"],
        description="E-mail учётной записи; ответ не зависит от того, есть ли такая",
    )


class PasswordResetConfirm(BaseModel):
    """New password by the link from the letter; the password never shows up in logs."""

    token: str = Field(
        min_length=1,
        max_length=RESET_TOKEN_MAX_LENGTH,
        description="Токен из ссылки письма (параметр token)",
    )
    password: SecretStr = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="Новый пароль; хранится только хэшем",
    )


class LoginInfo(BaseModel):
    """What the sign-in screen needs before a sign-in: the reset link or the contact (T-65)."""

    password_reset_available: bool = Field(
        description="SMTP настроен — на входе показывается ссылка «Забыли пароль?»"
    )
    support_contact: str = Field(
        examples=["admin@edu.vko.kz, +7 7232 00-00-00"],
        description="Контакт администратора, когда сброс недоступен; пусто — не показывать",
    )
