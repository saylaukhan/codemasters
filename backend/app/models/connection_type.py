"""``connection_types``: reference list of line technologies (fiber, ADSL, radio, ...)."""

from sqlalchemy import Identity
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConnectionType(TimestampMixin, Base):
    """Line technology; ``code`` is stable, ``name`` is shown in the panel."""

    __tablename__ = "connection_types"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
