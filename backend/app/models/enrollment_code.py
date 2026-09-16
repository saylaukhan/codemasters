"""``enrollment_codes``: one-time agent installation codes issued for a school (ADR-005)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EnrollmentCode(TimestampMixin, Base):
    """Installation code; only its hash is stored, ``used_at`` makes it one-time."""

    __tablename__ = "enrollment_codes"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    code_hash: Mapped[str] = mapped_column(unique=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
