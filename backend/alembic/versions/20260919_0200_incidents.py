"""Incident rules, incidents and their history (T-40; ТЗ п. 18, п. 19; ADR-007).

``incident_rules`` gets the defaults of «Решения по умолчанию»: one rule per metric, 3
violations in a row, restored after 2 normal results. Only «Нет соединения» also opens after 30
minutes — of heartbeat silence in working hours or from the first offline result of a run to
its last. The other metrics get no duration: hours lie between two measurements of a slot
schedule, so any two violations in a row would open an incident and N would mean nothing
(ADR-007 «Последствия»).

``incidents`` is scoped by its line like ``measurements``; ``incident_events`` follows the
incidents the scope sees. The panel may add events but never rewrite them. Numbers come from
``incident_number_seq``: one sequence for rule and manual incidents, never reset, so a number
is never reused.

Revision ID: 2a285a2760ee
Revises: 8b1f4d6e2c37
Create Date: 2026-09-19 02:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2a285a2760ee"
down_revision: str | None = "8b1f4d6e2c37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"
METRICS = (
    "'download_mbps', 'upload_mbps', 'ping_ms', 'jitter_ms', 'packet_loss_pct', 'no_connection'"
)
STATUSES = "'new', 'sent_to_provider', 'in_progress', 'awaiting_info', 'resolved', 'closed'"
LINES = "(SELECT rls_line_ids())::bigint[]"

# name, metric, N, T (minutes), M
DEFAULT_RULES = (
    ("Download ниже порога", "download_mbps", 3, None, 2),
    ("Upload ниже порога", "upload_mbps", 3, None, 2),
    ("Ping выше порога", "ping_ms", 3, None, 2),
    ("Jitter выше порога", "jitter_ms", 3, None, 2),
    ("Потери пакетов выше порога", "packet_loss_pct", 3, None, 2),
    ("Нет соединения", "no_connection", 3, 30, 2),
)


def timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "incident_rules",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("consecutive_violations", sa.BigInteger(), nullable=True),
        sa.Column("duration_min", sa.BigInteger(), nullable=True),
        sa.Column("recovery_normal_count", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(f"metric IN ({METRICS})", name=op.f("ck_incident_rules_metric")),
        sa.CheckConstraint(
            "consecutive_violations IS NOT NULL OR duration_min IS NOT NULL",
            name=op.f("ck_incident_rules_condition"),
        ),
        sa.CheckConstraint(
            "consecutive_violations >= 1", name=op.f("ck_incident_rules_consecutive_violations")
        ),
        sa.CheckConstraint("duration_min >= 1", name=op.f("ck_incident_rules_duration_min")),
        sa.CheckConstraint(
            "recovery_normal_count >= 1", name=op.f("ck_incident_rules_recovery_normal_count")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_rules")),
    )

    op.execute("CREATE SEQUENCE incident_number_seq")
    op.create_table(
        "incidents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=True),
        sa.Column("line_id", sa.BigInteger(), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("basis_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_violation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_provider_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responsible_user_id", sa.BigInteger(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_incidents_status")),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["incident_rules.id"], name=op.f("fk_incidents_rule_id_incident_rules")
        ),
        sa.ForeignKeyConstraint(["line_id"], ["lines.id"], name=op.f("fk_incidents_line_id_lines")),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_incidents_school_id_schools")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_incidents_provider_id_providers")
        ),
        sa.ForeignKeyConstraint(
            ["responsible_user_id"],
            ["users.id"],
            name=op.f("fk_incidents_responsible_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.UniqueConstraint("number", name=op.f("uq_incidents_number")),
    )
    for column in ("rule_id", "line_id", "school_id", "provider_id", "responsible_user_id"):
        op.create_index(op.f(f"ix_incidents_{column}"), "incidents", [column], unique=False)
    op.create_index("ix_incidents_started_at", "incidents", ["started_at"], unique=False)
    op.create_index(
        "uq_incidents_line_id_rule_id_open",
        "incidents",
        ["line_id", "rule_id"],
        unique=True,
        postgresql_where=sa.text(
            "rule_id IS NOT NULL AND restored_at IS NULL AND status NOT IN ('resolved', 'closed')"
        ),
    )

    op.create_table(
        "incident_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("incident_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('created', 'status_change', 'comment', 'restored')",
            name=op.f("ck_incident_events_kind"),
        ),
        sa.CheckConstraint(
            f"from_status IN ({STATUSES})", name=op.f("ck_incident_events_from_status")
        ),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name=op.f("ck_incident_events_to_status")),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], name=op.f("fk_incident_events_incident_id_incidents")
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], name=op.f("fk_incident_events_author_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_events")),
    )
    op.create_index(
        op.f("ix_incident_events_incident_id"), "incident_events", ["incident_id"], unique=False
    )
    op.create_index(
        op.f("ix_incident_events_author_user_id"),
        "incident_events",
        ["author_user_id"],
        unique=False,
    )

    # Scope of the panel (ADR-008): an incident by its line, an event by its incident.
    op.execute("ALTER TABLE incidents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY scope ON incidents "
        f"USING ((SELECT rls_scope()) = 'all' OR line_id = ANY ({LINES}))"
    )
    op.execute("ALTER TABLE incident_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY scope ON incident_events USING ((SELECT rls_scope()) = 'all' "
        f"OR incident_id IN (SELECT id FROM incidents WHERE line_id = ANY ({LINES})))"
    )
    # History is added to, never rewritten (ТЗ п. 19).
    op.execute(f"REVOKE UPDATE ON incident_events FROM {PANEL_ROLE}")

    for name, metric, count, minutes, recovery in DEFAULT_RULES:
        op.execute(
            sa.text(
                "INSERT INTO incident_rules "
                "(name, metric, consecutive_violations, duration_min, recovery_normal_count) "
                "VALUES (:name, :metric, :count, :minutes, :recovery)"
            ).bindparams(name=name, metric=metric, count=count, minutes=minutes, recovery=recovery)
        )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
