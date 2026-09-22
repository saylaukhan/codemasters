"""``users``: accounts of the panel (ТЗ п. 16, ADR-008)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Panel user; blocked with ``is_active = false`` and never deleted (ТЗ п. 16)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Login, stored lower-case: the login form compares it that way.
    email: Mapped[str] = mapped_column(unique=True)
    full_name: Mapped[str]
    # argon2 hash; the password itself is never stored (ТЗ п. 12).
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(ForeignKey("roles.code"), index=True)
    is_active: Mapped[bool] = mapped_column(server_default=true())
    # Chat of the user with the notification bot (T-42); empty — the Telegram channel is skipped
    # for him and the skip is written to ``notification_log``.
    telegram_chat_id: Mapped[str | None]
    # Language of the panel of this user (T-66, DESIGN.md §5.1); the browser keeps the same
    # choice, the profile makes it follow him to another computer and into his letters.
    locale: Mapped[str] = mapped_column(server_default=text("'ru'"))
    # Goes into every token of the user; logout raises it and every token issued before dies.
    token_version: Mapped[int] = mapped_column(server_default=text("0"))
    last_login_at: Mapped[datetime | None]
