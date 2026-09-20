"""Notifications of incidents and the journal of their delivery (T-42; ТЗ п. 18; ADR-007, ADR-008).

``notifications`` is one row per recipient: the panel channel itself, read by the bell and by
the stream. ``notification_log`` keeps every attempt of every channel, including the ones that
failed and the ones skipped because the channel is not configured (ТЗ п. 18); like ``audit_log``
and ``incident_events`` it is only added to, so the panel role loses UPDATE on it.

Scope here is the user, not his district: a notification belongs to the person it was written
for, and even Область must not read someone else's bell. RLS therefore reads ``app.user_id``,
set next to ``app.user_scope`` by ``app/auth/rls.py``; Celery writes the rows as the owner of the
tables, outside any scope. ``users.telegram_chat_id`` is where the Telegram channel sends;
empty means the channel is skipped for that user.

Revision ID: 4f8b1c6e3a57
Revises: 2a285a2760ee
Create Date: 2026-09-20 11:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f8b1c6e3a57"
down_revision: str | None = "2a285a2760ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"
KINDS = "'incident_opened', 'incident_status_changed', 'incident_restored'"
CHANNELS = "'panel', 'telegram', 'email'"
RESULTS = "'sent', 'failed', 'skipped'"

# Id of the panel user of the request; empty outside a panel request (Celery, the agent API).
USER_ID_FUNCTION = """
CREATE FUNCTION rls_user_id() RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.user_id', true), '')::bigint
$$
"""


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
    op.add_column("users", sa.Column("telegram_chat_id", sa.Text(), nullable=True))

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("incident_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_notifications_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], name=op.f("fk_notifications_incident_id_incidents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_notifications_incident_id"), "notifications", ["incident_id"], unique=False
    )
    # The panel reads one user newest first; the counter of the bell asks only for the unread.
    op.create_index(
        "ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_notifications_user_id_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.create_table(
        "notification_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"channel IN ({CHANNELS})", name=op.f("ck_notification_log_channel")),
        sa.CheckConstraint(f"result IN ({RESULTS})", name=op.f("ck_notification_log_result")),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_notification_log_notification_id_notifications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_log")),
    )
    op.create_index(
        op.f("ix_notification_log_notification_id"),
        "notification_log",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_log_created_at"), "notification_log", ["created_at"], unique=False
    )

    op.execute(USER_ID_FUNCTION)
    # A notification belongs to its user, not to his district: the scope of ADR-008 decides who
    # gets one, this policy decides who may read it back.
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY scope ON notifications USING (user_id = (SELECT rls_user_id()))")
    op.execute("ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY scope ON notification_log USING (notification_id IN "
        "(SELECT id FROM notifications WHERE user_id = (SELECT rls_user_id())))"
    )
    # The journal of the deliveries is added to, never rewritten (ТЗ п. 18).
    op.execute(f"REVOKE UPDATE ON notification_log FROM {PANEL_ROLE}")


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
