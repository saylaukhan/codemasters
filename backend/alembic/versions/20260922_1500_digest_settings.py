"""Сводка для руководителя: расписания рассылки и запись отправки (T-67, §6.2 дизайна).

``digest_settings`` is one mailing of one scope: the whole oblast or one district, the weekday
and the hour of the send in ``settings.timezone``, the addresses, the Telegram chat and the
moment of the last send. The schedule lives here and nowhere in the code (ТЗ п. 11, п. 20;
ADR-004), and ``last_sent_at`` is what keeps the hourly beat task from sending one issue twice.

The table has no RLS policy: it is an administration resource, like ``threshold_profiles``,
``schedules`` and ``incident_rules``, and every endpoint of it requires ``settings:manage``,
which only Область and Администратор have — and their scope is the whole oblast (ADR-008).
A mailing is a setting and not history, so the panel role gets DELETE on this one table:
everywhere else it still may not delete (ТЗ п. 16, migration of T-20).

A send needs a ``notifications`` row, because ``notification_log.notification_id`` is NOT NULL
(ТЗ п. 18, invariant 10 of AGENTS.md §8), and a digest belongs to neither one user nor one
incident: the kind ``digest_sent`` joins the check constraint and carries both columns empty,
which the new constraint states as an equivalence. The bell never shows such a row — it joins
``incidents`` — and the RLS policy of T-42 compares ``user_id`` with the reader, so NULL matches
nobody.

Revision ID: c3d9f1a7b6e4
Revises: d5b9a3c71e42
Create Date: 2026-09-22 12:00:00.000000+05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d9f1a7b6e4"
down_revision: str | None = "e7a4c2b81f36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PANEL_ROLE = "vko_panel"
SCOPES = "'oblast', 'region'"
KINDS = "'incident_opened', 'incident_status_changed', 'incident_restored', 'digest_sent'"
# A digest notification has neither a user nor an incident; every other kind has both.
DIGEST_TARGET = "(kind = 'digest_sent') = (user_id IS NULL AND incident_id IS NULL)"


def upgrade() -> None:
    op.create_table(
        "digest_settings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("weekday", sa.BigInteger(), nullable=False),
        sa.Column("hour", sa.BigInteger(), nullable=False),
        sa.Column(
            "recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("telegram_chat_id", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(f"scope IN ({SCOPES})", name=op.f("ck_digest_settings_scope")),
        sa.CheckConstraint(
            "(region_id IS NOT NULL) = (scope = 'region')",
            name=op.f("ck_digest_settings_region_target"),
        ),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name=op.f("ck_digest_settings_weekday")),
        sa.CheckConstraint("hour BETWEEN 0 AND 23", name=op.f("ck_digest_settings_hour")),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_digest_settings_region_id_regions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digest_settings")),
    )
    op.create_index(op.f("ix_digest_settings_region_id"), "digest_settings", ["region_id"])
    # The beat task asks once an hour for the rows of this weekday and hour that are switched on.
    op.create_index(
        "ix_digest_settings_weekday_hour",
        "digest_settings",
        ["weekday", "hour"],
        postgresql_where=sa.text("is_active"),
    )
    op.execute(f"GRANT DELETE ON digest_settings TO {PANEL_ROLE}")

    # The name goes through NAMING_CONVENTION of app/models/base.py, exactly like the
    # ``create_check_constraint`` below: "kind" becomes ``ck_notifications_kind`` in the
    # database. Passing the full name here would ask for ``ck_notifications_ck_…_kind``.
    op.drop_constraint("kind", "notifications", type_="check")
    op.alter_column("notifications", "user_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column("notifications", "incident_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_check_constraint("kind", "notifications", f"kind IN ({KINDS})")
    op.create_check_constraint("digest_target", "notifications", DIGEST_TARGET)


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
