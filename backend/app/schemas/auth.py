"""Requests and responses of panel authentication (plan.md §10, ADR-008, ADR-009).

Passwords are checked against argon2 hashes (ТЗ п. 12). Personal data here is limited to the
user's own e-mail and full name.
"""

from pydantic import BaseModel, Field, SecretStr

from app.schemas.statuses import UserRole

# Upper bound of a password: argon2 hashes whatever it gets, a cap keeps login cheap.
PASSWORD_MAX_LENGTH = 128


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
