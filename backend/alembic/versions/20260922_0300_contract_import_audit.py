"""Audit of the contract import (T-61; ТЗ п. 14, п. 16): ``audit_log.action`` accepts ``import``.

An import of a contract registry changes many lines in one request; the audit log keeps one
record of it — the file, how many rows it had and how many lines were created and changed — as
an ``import`` of lines rather than a ``create`` of nothing (ADR-008).

Revision ID: b5d1e7a3c906
Revises: 6c2f8d4e9b71
Create Date: 2026-09-22 03:00:00.000000+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d1e7a3c906"
down_revision: str | None = "6c2f8d4e9b71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_ACTIONS = (
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


def upgrade() -> None:
    op.drop_constraint(op.f("ck_audit_log_action"), "audit_log", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_log_action"),
        "audit_log",
        f"action IN ({', '.join(repr(value) for value in AUDIT_ACTIONS)})",
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
