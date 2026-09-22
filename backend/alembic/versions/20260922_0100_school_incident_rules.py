"""Incident rules of one school (T-59; ТЗ п. 18, п. 20; ADR-007).

``incident_rules`` gets a scope. ``global`` is every rule that exists today: it watches every
line of the oblast. ``school`` is a rule of the lines of one school: for that school it replaces
the global rule of the same metric, so a school on a satellite link may need five violations
in a row where the oblast needs three, without touching anyone else. The detection reads the
rules anew on every run, so a change applies to the next one (T-40).

The column is added with the default ``global``, so nothing changes for an installation that
is already running; a rule of a school names its school and nothing else.

Revision ID: 3e7b9c1d5a24
Revises: 9a1c5e7b3d08
Create Date: 2026-09-22 01:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e7b9c1d5a24"
down_revision: str | None = "9a1c5e7b3d08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incident_rules",
        sa.Column("scope", sa.Text(), server_default=sa.text("'global'"), nullable=False),
    )
    op.add_column("incident_rules", sa.Column("school_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_incident_rules_school_id_schools"),
        "incident_rules",
        "schools",
        ["school_id"],
        ["id"],
    )
    op.create_index(op.f("ix_incident_rules_school_id"), "incident_rules", ["school_id"])
    op.create_check_constraint(
        op.f("ck_incident_rules_scope"), "incident_rules", "scope IN ('global', 'school')"
    )
    op.create_check_constraint(
        op.f("ck_incident_rules_school_target"),
        "incident_rules",
        "(school_id IS NOT NULL) = (scope = 'school')",
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
