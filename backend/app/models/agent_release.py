"""``agent_releases``: published MSI builds of the agent for self-update (plan.md §4.6)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Identity, Index, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentRelease(TimestampMixin, Base):
    """Agent release; ``latest_version`` of the agent configuration comes from here (T-17).

    Pilot agents get a release first and the rest after it is promoted to ``stable`` (T-50).
    A release is withdrawn with ``is_active``, never deleted: the hash of a published MSI must
    stay checkable.
    """

    __tablename__ = "agent_releases"
    __table_args__ = (
        CheckConstraint("channel IN ('pilot', 'stable')", name="channel"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        Index("ix_agent_releases_channel_released_at", "channel", "released_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    version: Mapped[str] = mapped_column(unique=True)
    channel: Mapped[str]
    download_url: Mapped[str]
    # SHA-256 of the MSI, lowercase hex: the agent refuses a build that does not match it.
    sha256: Mapped[str]
    notes: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(server_default=true())
    released_at: Mapped[datetime] = mapped_column(server_default=func.now())
