"""Audit of monitoring points (T-35): ``audit_log.entity_type`` accepts ``monitoring_point``.

The admin panel creates points and binds them to lines; each change is an audit record like
the changes of lines and contacts (ТЗ п. 16, ADR-008).

Revision ID: 8b1e4f6a2c93
Revises: 5d2f9a3c7e18
Create Date: 2026-09-18 23:00:02.515734+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b1e4f6a2c93"
down_revision: str | None = "5d2f9a3c7e18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_ENTITY_TYPES = (
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
    "export",
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_audit_log_entity_type"), "audit_log", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_log_entity_type"),
        "audit_log",
        f"entity_type IN ({', '.join(repr(value) for value in AUDIT_ENTITY_TYPES)})",
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
