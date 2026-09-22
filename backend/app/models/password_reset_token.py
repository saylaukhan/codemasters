"""``password_reset_tokens``: one-time links of «Забыли пароль?» (T-65; ADR-005)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PasswordResetToken(Base):
    """Reset link; only the sha256 of its secret is stored, ``used_at`` makes it one-time."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
