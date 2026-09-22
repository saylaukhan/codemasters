"""Календарь каникул, праздников и плановых работ (T-70, docs/design/README.md §6.5).

``calendar_events`` is one period the monitoring keeps quiet about: ``vacation`` and ``holiday``
cover whole local days of ``settings.timezone``, ``planned_works`` is a window of one provider.
The target is the whole oblast, one district or one school, and the RLS policy reads it from
``app.user_scope`` like the neighbouring scoped tables (ADR-008): a district sees the events of
the oblast and of its own district, a school those of its own school, and writes are narrower
than reads — an oblast-wide event is entered by Область and Администратор only.

An event is a setting and not history, so the panel role gets DELETE on this one table, as it
has on ``digest_settings`` (T-67); everywhere else it still may not delete (ТЗ п. 16).

Revision ID: b8e1c4a90d75
Revises: f1a6d24b9c83
Create Date: 2026-09-22 19:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e1c4a90d75"
down_revision: str | None = "f1a6d24b9c83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"
KINDS = "'vacation', 'holiday', 'planned_works'"
SCOPES = "'oblast', 'district', 'school'"
SCHOOLS = "(SELECT rls_school_ids())::bigint[]"
REGIONS = "(SELECT rls_region_ids())::bigint[]"

# Districts the reader may see: his own, the one of his school, those of the schools he serves.
# SECURITY DEFINER like the neighbouring helpers of T-20, so a policy never reads a policy.
REGION_IDS = """
    CREATE FUNCTION rls_region_ids() RETURNS bigint[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        SELECT CASE split_part(rls_scope(), ':', 1)
            WHEN 'region' THEN ARRAY[rls_scope_id('region')]
            ELSE ARRAY(
                SELECT DISTINCT region_id FROM schools
                WHERE id = ANY ((SELECT rls_school_ids())::bigint[]))
        END
    $$
"""

# Read: the events of the whole oblast are everybody's. Write: only of one's own district or
# school, so an event of the oblast is entered by a scope that covers it.
READABLE = (
    f"(SELECT rls_scope()) = 'all' OR scope = 'oblast' "
    f"OR region_id = ANY ({REGIONS}) OR school_id = ANY ({SCHOOLS})"
)
WRITABLE = (
    f"(SELECT rls_scope()) = 'all' OR region_id = ANY ({REGIONS}) OR school_id = ANY ({SCHOOLS})"
)


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("school_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_calendar_events_kind")),
        sa.CheckConstraint(f"scope IN ({SCOPES})", name=op.f("ck_calendar_events_scope")),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) = (scope = 'district')",
            name=op.f("ck_calendar_events_district_target"),
        ),
        sa.CheckConstraint(
            "(school_id IS NOT NULL) = (scope = 'school')",
            name=op.f("ck_calendar_events_school_target"),
        ),
        sa.CheckConstraint(
            "provider_id IS NULL OR kind = 'planned_works'",
            name=op.f("ck_calendar_events_provider_of_planned_works"),
        ),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_calendar_events_period")),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_calendar_events_region_id_regions")
        ),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_calendar_events_school_id_schools")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_calendar_events_provider_id_providers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_events")),
    )
    op.create_index(op.f("ix_calendar_events_region_id"), "calendar_events", ["region_id"])
    op.create_index(op.f("ix_calendar_events_school_id"), "calendar_events", ["school_id"])
    op.create_index(op.f("ix_calendar_events_provider_id"), "calendar_events", ["provider_id"])
    op.create_index(
        op.f("ix_calendar_events_starts_at_ends_at"), "calendar_events", ["starts_at", "ends_at"]
    )

    op.execute(REGION_IDS)
    op.execute("ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY scope ON calendar_events USING ({READABLE}) WITH CHECK ({WRITABLE})")
    op.execute(f"GRANT DELETE ON calendar_events TO {PANEL_ROLE}")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
