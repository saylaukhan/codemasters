"""Appeals to providers and their history (T-48; ТЗ п. 17; ADR-011, ADR-007).

``appeals`` holds only sent letters: a draft is built on every request and stored nowhere
(T-47), so a row here always has a number, a PDF and a moment of sending. Numbers come from
``appeal_number_seq`` — one sequence, never reset, so a number is never reused, as the incidents
of T-40 do it.

``appeals`` is scoped by its line like ``incidents``, so a provider sees the appeals of its own
lines and nothing else (ADR-008); ``appeal_events`` follows the appeals the scope sees. The
panel may add events but never rewrite them: the history of ТЗ п. 17 is what happened.

Revision ID: 7c4d9e2b1a63
Revises: 4f8b1c6e3a57
Create Date: 2026-09-20 23:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7c4d9e2b1a63"
down_revision: str | None = "4f8b1c6e3a57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"
STATUSES = "'new', 'sent_to_provider', 'in_progress', 'awaiting_info', 'resolved', 'closed'"
LINES = "(SELECT rls_line_ids())::bigint[]"


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
    op.execute("CREATE SEQUENCE appeal_number_seq")
    op.create_table(
        "appeals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("incident_id", sa.BigInteger(), nullable=True),
        sa.Column("line_id", sa.BigInteger(), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("user_comment", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recipient_email", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.Text(), nullable=False),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_appeals_status")),
        sa.CheckConstraint(
            "delivery_status IN ('sent', 'not_sent')", name=op.f("ck_appeals_delivery_status")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], name=op.f("fk_appeals_incident_id_incidents")
        ),
        sa.ForeignKeyConstraint(["line_id"], ["lines.id"], name=op.f("fk_appeals_line_id_lines")),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], name=op.f("fk_appeals_school_id_schools")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_appeals_provider_id_providers")
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], name=op.f("fk_appeals_author_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeals")),
        sa.UniqueConstraint("number", name=op.f("uq_appeals_number")),
    )
    for column in ("incident_id", "line_id", "school_id", "provider_id", "author_user_id"):
        op.create_index(op.f(f"ix_appeals_{column}"), "appeals", [column], unique=False)
    op.create_index("ix_appeals_sent_at", "appeals", ["sent_at"], unique=False)

    op.create_table(
        "appeal_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("appeal_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('sent', 'status_change', 'comment')", name=op.f("ck_appeal_events_kind")
        ),
        sa.CheckConstraint(
            f"from_status IN ({STATUSES})", name=op.f("ck_appeal_events_from_status")
        ),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name=op.f("ck_appeal_events_to_status")),
        sa.ForeignKeyConstraint(
            ["appeal_id"], ["appeals.id"], name=op.f("fk_appeal_events_appeal_id_appeals")
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], name=op.f("fk_appeal_events_author_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_events")),
    )
    op.create_index(op.f("ix_appeal_events_appeal_id"), "appeal_events", ["appeal_id"])
    op.create_index(op.f("ix_appeal_events_author_user_id"), "appeal_events", ["author_user_id"])

    # Scope of the panel (ADR-008): an appeal by its line, an event by its appeal.
    op.execute("ALTER TABLE appeals ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY scope ON appeals "
        f"USING ((SELECT rls_scope()) = 'all' OR line_id = ANY ({LINES}))"
    )
    op.execute("ALTER TABLE appeal_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY scope ON appeal_events USING ((SELECT rls_scope()) = 'all' "
        f"OR appeal_id IN (SELECT id FROM appeals WHERE line_id = ANY ({LINES})))"
    )
    # History is added to, never rewritten (ТЗ п. 17).
    op.execute(f"REVOKE UPDATE ON appeal_events FROM {PANEL_ROLE}")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
