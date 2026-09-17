"""Number of measurements below the contract in m_hourly and m_daily (T-19, ТЗ п. 14).

``GET /api/analytics`` promises the share of measurements below the contract speed, and the
rule «устойчивое несоответствие договору» of ТЗ п. 14 counts them over seven days; both read
the aggregates only (plan.md §5), so the number has to be in them. A continuous aggregate
cannot gain a column, so both views are recreated — the revision that created them is already
in ``developing`` and is not touched (ADR-003, CONTRIBUTING.md §6).

``contract_ok`` is empty when there is nothing to compare — no contract speeds on the line,
nothing measured, Wi-Fi — so only an explicit ``false`` counts (T-18, ADR-004).

Revision ID: c1a7d35b8e60
Revises: b6e2f04c7a18
Create Date: 2026-09-18 03:30:41.906223+05:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a7d35b8e60"
down_revision: str | None = "b6e2f04c7a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Boundaries of an hour and of a day are the local ones of the school (ADR-014, T-19).
TIMEZONE = "Asia/Almaty"

# Statuses of a measurement that are not «Норма» (ADR-004).
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
    """Continuous aggregate ``name`` of ``measurements`` over buckets ``bucket`` wide."""
    return f"""
        CREATE MATERIALIZED VIEW {name}
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket(INTERVAL '{bucket}', measured_at, '{TIMEZONE}') AS bucket,
               line_id,
               device_id,
               count(*) AS measurements_count,
               sum(CASE WHEN quality_status IN ({PROBLEM_STATUSES}) THEN 1 ELSE 0 END)
                   AS problem_count,
               sum(CASE WHEN contract_ok IS FALSE THEN 1 ELSE 0 END) AS below_contract_count,
               {metrics()}
        FROM measurements
        WHERE {RATES_THE_LINE}
        GROUP BY bucket, line_id, device_id
        WITH NO DATA
    """


def policy(name: str, *, start_offset: str, schedule_interval: str) -> str:
    """Refresh policy of ``name``: how far back it looks and how often it wakes up."""
    return (
        f"SELECT add_continuous_aggregate_policy('{name}', "
        f"start_offset => INTERVAL '{start_offset}', "
        "end_offset => INTERVAL '1 hour', "
        f"schedule_interval => INTERVAL '{schedule_interval}')"
    )


def upgrade() -> None:
    # Dropping a view takes its refresh policy with it; nothing is materialized yet, so there
    # is nothing to lose — the views answer from the hypertable until the policy runs.
    op.execute("DROP MATERIALIZED VIEW m_daily")
    op.execute("DROP MATERIALIZED VIEW m_hourly")
    op.execute(aggregate("m_hourly", "1 hour"))
    op.execute(aggregate("m_daily", "1 day"))
    op.execute(policy("m_hourly", start_offset="30 days", schedule_interval="30 minutes"))
    op.execute(policy("m_daily", start_offset="90 days", schedule_interval="1 hour"))


def downgrade() -> None:
    # Forward-only migrations (ADR-003, CONTRIBUTING.md §6): a mistake is fixed by a new revision.
    raise NotImplementedError("forward-only migration: downgrade is not supported")
