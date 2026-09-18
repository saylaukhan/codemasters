"""Row-level security by ``app.user_scope`` on the tables with a visibility scope (T-20, ADR-008).

Panel requests run as the role ``vko_panel`` (``app/auth/rls.py``); the owner of the tables —
agent requests, the login, migrations, Celery — is not subject to the policies. The scope is
``all``, ``region:<id>``, ``school:<id>`` or ``provider:<id>``; anything else sees nothing.
Школа and Район/город see every line of their schools; Провайдер sees its own lines only, their
points, devices and measurements, and the schools those lines serve (ТЗ п. 16).

The id lists are computed by SECURITY DEFINER functions: they read ``schools`` and ``lines``
as the owner, so a policy never recurses into another policy. Policies call them through a
sub-select, which PostgreSQL evaluates once per query (an InitPlan), not once per row.

``vko_panel`` gets SELECT, INSERT and UPDATE, never DELETE: the panel blocks and deactivates,
it does not delete (ТЗ п. 16, п. 20). The role is cluster-wide, so it is created only once.

Revision ID: e7c3a9d15b42
Revises: d4b8e21f6a90
Create Date: 2026-09-18 15:10:37.221904+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c3a9d15b42"
down_revision: str | None = "d4b8e21f6a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"

# Visible when the scope is the whole oblast or the column is in the list of the scope.
# The cast makes the sub-select an array expression: bare, ANY would read it as a sub-query.
SCHOOLS = "(SELECT rls_school_ids())::bigint[]"
LINES = "(SELECT rls_line_ids())::bigint[]"
DEVICES = "(SELECT rls_device_ids())::bigint[]"
POLICIES = {
    "schools": ("id", SCHOOLS),
    "school_contacts": ("school_id", SCHOOLS),
    "enrollment_codes": ("school_id", SCHOOLS),
    "lines": ("id", LINES),
    "monitoring_points": ("line_id", LINES),
    "outages": ("line_id", LINES),
    "measurements": ("line_id", LINES),
    "devices": ("id", DEVICES),
    "heartbeats": ("device_id", DEVICES),
}

# One statement per execute: asyncpg prepares each one and refuses several at once.
FUNCTIONS = (
    """
    CREATE FUNCTION rls_scope() RETURNS text
    LANGUAGE sql STABLE AS $$
        SELECT coalesce(current_setting('app.user_scope', true), '')
    $$
    """,
    """
    CREATE FUNCTION rls_scope_id(kind text) RETURNS bigint
    LANGUAGE sql STABLE AS $$
        SELECT CASE WHEN split_part(rls_scope(), ':', 1) = kind
                    THEN nullif(split_part(rls_scope(), ':', 2), '')::bigint END
    $$
    """,
    """
    CREATE FUNCTION rls_school_ids() RETURNS bigint[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        SELECT CASE split_part(rls_scope(), ':', 1)
            WHEN 'school' THEN ARRAY[rls_scope_id('school')]
            WHEN 'region' THEN ARRAY(
                SELECT id FROM schools WHERE region_id = rls_scope_id('region'))
            WHEN 'provider' THEN ARRAY(
                SELECT DISTINCT school_id FROM lines WHERE provider_id = rls_scope_id('provider'))
            ELSE ARRAY[]::bigint[]
        END
    $$
    """,
    """
    CREATE FUNCTION rls_line_ids() RETURNS bigint[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        SELECT CASE split_part(rls_scope(), ':', 1)
            WHEN 'provider' THEN ARRAY(
                SELECT id FROM lines WHERE provider_id = rls_scope_id('provider'))
            ELSE ARRAY(
                SELECT id FROM lines
                WHERE school_id = ANY ((SELECT rls_school_ids())::bigint[]))
        END
    $$
    """,
    """
    CREATE FUNCTION rls_device_ids() RETURNS bigint[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        SELECT ARRAY(
            SELECT d.id FROM devices d
            JOIN monitoring_points p ON p.id = d.monitoring_point_id
            WHERE p.line_id = ANY ((SELECT rls_line_ids())::bigint[]))
    $$
    """,
)


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PANEL_ROLE}') THEN
                CREATE ROLE {PANEL_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    # The application switches to the role with SET ROLE, which needs membership.
    op.execute(f"GRANT {PANEL_ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {PANEL_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {PANEL_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {PANEL_ROLE}")
    op.execute(f"REVOKE ALL ON alembic_version FROM {PANEL_ROLE}")
    # Tables of later migrations get the same grants without repeating them.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE ON TABLES TO {PANEL_ROLE}"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {PANEL_ROLE}"
    )

    for function in FUNCTIONS:
        op.execute(function)
    for table, (column, visible_ids) in POLICIES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY scope ON {table} "
            f"USING ((SELECT rls_scope()) = 'all' OR {column} = ANY ({visible_ids}))"
        )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
