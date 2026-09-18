"""``user_scopes``: what part of VKO a user sees (ADR-008).

Школа — ``school_id``, Район/город — ``region_id``, Провайдер — ``provider_id``; Область and
Администратор see the whole oblast and have no row. RLS reads the scope through
``app.user_scope`` (``app/auth/rls.py``).
"""

from sqlalchemy import CheckConstraint, ForeignKey, Identity
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserScope(TimestampMixin, Base):
    """Scope of one user: exactly one of the three ids is set."""

    __tablename__ = "user_scopes"
    __table_args__ = (
        CheckConstraint("num_nonnulls(region_id, provider_id, school_id) = 1", name="one_scope"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), index=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True)
