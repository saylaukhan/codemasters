"""``settings``: the single row of system-wide values changed in the admin panel (T-37).

``make seed`` stores the initial values from the environment; after that the database is the
source of truth, and agents get their part from ``GET /api/agent/config`` (T-17, ADR-012).
T-05 adds the measurement servers; the other values of ``SettingsDetail`` arrive with the tasks
that use them.
"""

from sqlalchemy import CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemSettings(TimestampMixin, Base):
    """System settings; the table holds at most one row, ``id = 1``."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, server_default=text("1"))
    # Main measurement server and the ndt7 fallback; NULL means no fallback (ADR-012).
    librespeed_url: Mapped[str]
    ndt7_url: Mapped[str | None]
