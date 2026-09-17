"""Continuous aggregates m_hourly and m_daily over the hours and days of Asia/Almaty (T-19).

Analytics, the rating of schools and the heat map «час × день» read these views and never the
raw ``measurements`` (ТЗ п. 5, plan.md §5). The buckets are cut by the local day of a school:
a measurement at 02:00 Asia/Almaty belongs to that day and not to the previous UTC one — this
is the question ADR-014 left open and Asia/Almaty is the answer to it. Storage stays UTC:
``bucket`` is a ``timestamptz`` like every other moment.

Wi-Fi measurements are left out: they measure the air, not the line (ADR-012), and these
rollups are what a line and its provider are judged by. They stay in ``measurements``.

``materialized_only = false`` keeps the views correct between refreshes: what the policy has
not materialized yet is read straight from the hypertable, so the current hour and the current
day are never missing. The window of the hourly policy is 30 days because an agent may resend
a queue that old (ADR-006, «Решения по умолчанию»); a refresh over it is cheap, as TimescaleDB
recomputes only the buckets its invalidation log marks as changed.

Revision ID: b6e2f04c7a18
Revises: 7c41b0ad5e93
Create Date: 2026-09-18 03:00:12.774310+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6e2f04c7a18"
down_revision: str | None = "7c41b0ad5e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Boundaries of an hour and of a day are the local ones of the school (ADR-014, T-19).
TIMEZONE = "Asia/Almaty"

# Statuses of a measurement that are not «Норма» (ADR-004): the share of them is the quality
# of the period in every report of ТЗ п. 5.
PROBLEM_STATUSES = "'unstable', 'critical', 'offline'"

# Wi-Fi does not rate the line, and NULL means the agent did not name the interface (ADR-012).
RATES_THE_LINE = "iface_type IS DISTINCT FROM 'wifi'"


def metrics() -> str:
    """avg / min / max of every metric of ТЗ п. 2, in the order of the export of ТЗ п. 9."""
    return ",\n               ".join(
        f"{aggregate}({column}) AS {aggregate}_{column}"
        for column in ("download_mbps", "upload_mbps", "ping_ms", "jitter_ms", "packet_loss_pct")
        for aggregate in ("avg", "min", "max")
    )


def aggregate(name: str, bucket: str) -> str:
    """Continuous aggregate ``name`` of ``measurements`` over buckets ``bucket`` wide.

    ``WITH NO DATA`` is what lets the statement run inside the transaction of the migration;
    the view answers from the hypertable until the policy below materializes the first buckets.
    """
    return f"""
        CREATE MATERIALIZED VIEW {name}
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket(INTERVAL '{bucket}', measured_at, '{TIMEZONE}') AS bucket,
               line_id,
               device_id,
               count(*) AS measurements_count,
               sum(CASE WHEN quality_status IN ({PROBLEM_STATUSES}) THEN 1 ELSE 0 END)
                   AS problem_count,
               {metrics()}
        FROM measurements
        WHERE {RATES_THE_LINE}
        GROUP BY bucket, line_id, device_id
        WITH NO DATA
    """


def policy(name: str, *, start_offset: str, schedule_interval: str) -> str:
    """Refresh policy of ``name``: how far back it looks and how often it wakes up.

    ``end_offset`` is one hour, so a bucket is materialized once it can no longer change much;
    everything newer than that is served by real-time aggregation.
    """
    return (
        f"SELECT add_continuous_aggregate_policy('{name}', "
        f"start_offset => INTERVAL '{start_offset}', "
        "end_offset => INTERVAL '1 hour', "
        f"schedule_interval => INTERVAL '{schedule_interval}')"
    )


def upgrade() -> None:
    op.execute(aggregate("m_hourly", "1 hour"))
    op.execute(aggregate("m_daily", "1 day"))
    op.execute(policy("m_hourly", start_offset="30 days", schedule_interval="30 minutes"))
    op.execute(policy("m_daily", start_offset="90 days", schedule_interval="1 hour"))


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
