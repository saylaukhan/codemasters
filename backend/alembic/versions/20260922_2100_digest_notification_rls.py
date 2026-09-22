"""Строка сводки под ролью панели: политика RLS ``notifications`` (T-81, дефект T-67).

The migration of T-67 let ``notifications.user_id`` and ``incident_id`` be empty for one kind,
``digest_sent``: a digest belongs to no user and to no incident, and the check constraint
``ck_notifications_digest_target`` states that as an equivalence. The policy of T-42 was left as
it was — ``USING (user_id = rls_user_id())`` — and a policy without ``WITH CHECK`` is also what
PostgreSQL applies to an INSERT, so a row with an empty ``user_id`` compares ``NULL = <id>``,
gets NULL, and the insert is refused: «new row violates row-level security policy». The mailing
by the schedule never noticed — the worker opens its own session and goes as the owner of the
table (``app/workers/tasks/digest.py``) — but «Отправить сейчас» of the administration runs in
the panel session and could not write its row at all.

Both policies are rewritten so that a digest row is one of their own. The row must also be
readable, not only writable: the ORM inserts it with ``RETURNING id``, and PostgreSQL applies
the SELECT policy to what RETURNING gives back. Reading it back costs nothing: a digest carries
the same numbers the panel shows on the main screen and no personal data (ТЗ п. 15; ADR-011),
and no endpoint returns such a row anyway — the bell and the list of notifications filter by
``user_id`` of the reader (``app/services/notifications.py``), and the query that renders one
joins ``users`` by an inner join, which an empty ``user_id`` never passes. The journal of the
deliveries follows its notification, as it did before, so the attempts of a digest stay with it.

Revision ID: d4f8b2e6c917
Revises: b8e3d7a12f64
Create Date: 2026-09-22 21:00:00.000000+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8b2e6c917"
down_revision: str | None = "b8e3d7a12f64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A digest is the one notification of nobody (ck_notifications_digest_target, T-67).
DIGEST_ROW = "(kind = 'digest_sent' AND user_id IS NULL)"
OWN_ROW = "user_id = (SELECT rls_user_id())"


def upgrade() -> None:
    op.execute("DROP POLICY scope ON notifications")
    op.execute(f"CREATE POLICY scope ON notifications USING ({OWN_ROW} OR {DIGEST_ROW})")
    op.execute("DROP POLICY scope ON notification_log")
    op.execute(
        "CREATE POLICY scope ON notification_log USING (notification_id IN "
        f"(SELECT id FROM notifications WHERE {OWN_ROW} OR {DIGEST_ROW}))"
    )


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
