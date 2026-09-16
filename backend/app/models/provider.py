"""``providers``: internet service providers serving school lines (ADR-003)."""

from sqlalchemy import Identity
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Provider(TimestampMixin, Base):
    """Internet service provider; the scope of the Provider role (ADR-008)."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
