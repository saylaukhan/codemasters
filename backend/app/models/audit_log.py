"""``audit_log``: sign-ins, changing actions of the panel, rejected agent requests.

Written by the login endpoint and by the audit middleware (``app/auth/audit.py``); a trigger of
the migration rejects UPDATE and DELETE, so a record outlives a blocked user (ТЗ п. 12, п. 16).
Passwords, tokens and installation codes never get here.
"""

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Codes of ``AuditAction`` and ``AuditEntityType`` in ``app/schemas/audit.py``.
ACTIONS = (
    "login_success",
    "login_failure",
    "create",
    "update",
    "block",
    "unblock",
    "password_reset",
    "status_change",
    "export",
    "import",
    "transfer_error",
)
ENTITY_TYPES = (
    "user",
    "school",
    "line",
    "monitoring_point",
    "school_contact",
    "device",
    "enrollment_code",
    "region",
    "provider",
    "connection_type",
    "threshold_profile",
    "schedule",
    "setting",
    "incident_rule",
    "agent_release",
    "incident",
    "appeal",
    "appeal_template",
    "export",
)


def one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class AuditLog(Base):
    """One audit record: who, when, what; the codes are those of ``app/schemas/audit.py``."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(one_of("action", ACTIONS), name="action"),
        CheckConstraint(one_of("entity_type", ENTITY_TYPES), name="entity_type"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    # Empty for an agent request or a sign-in with an unknown e-mail.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    # E-mail at the moment of the action; for login_failure — the one typed.
    user_email: Mapped[str | None]
    action: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[int | None]
    changes: Mapped[dict[str, Any] | None]
    error_type: Mapped[str | None]
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
