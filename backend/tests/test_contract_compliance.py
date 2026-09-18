"""T-29: sustained mismatch of the main line with its contract (ТЗ п. 14, «Решения по умолчанию»).

More than 50 % of the measurements of the main line over 7 days below the contract speed is a
sustained mismatch; both numbers come from ``settings``. Only measurements with ``contract_ok``
count: an older one, a Wi-Fi one and one without a verdict stay outside the share.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from pytest import approx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, Measurement, Provider, School
from app.services.status import recompute_contract_compliance
from app.workers.celery_app import celery_app
from app.workers.tasks.contracts import RECOMPUTE_CONTRACT_COMPLIANCE
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

NOW = datetime.now(UTC)


def measurement(device_id: int, line_id: int, **values: Any) -> Measurement:
    defaults = {"connection_status": "online", "iface_type": "ethernet", "quality_status": "normal"}
    return Measurement(
        measurement_uuid=uuid.uuid4(),
        device_id=device_id,
        line_id=line_id,
        thresholds_snapshot={},
        **(defaults | values),
    )


async def school_below_contract(
    session: AsyncSession, code: str, *, below: int, total: int
) -> tuple[School, Line]:
    """School whose main line of 50 Mbit/s by contract had ``below`` of ``total`` measurements
    of the last days under the contract, plus ones that must not count: an old one below the
    contract, a Wi-Fi one and one with nothing to compare; and a reserve line."""
    school = await create_school(session, school_code=code)
    device, _ = await register_device(
        session, await primary_point(session, school), device_uid=code
    )
    main = (await session.scalars(select(Line).where(Line.school_id == school.id))).one()
    main.contract_down_mbps = 50
    reserve_provider = Provider(name=f"Резерв {code}")
    session.add(reserve_provider)
    await session.flush()
    session.add(Line(school_id=school.id, provider_id=reserve_provider.id, status="reserve"))
    for i in range(total):
        session.add(
            measurement(
                device.id,
                main.id,
                measured_at=NOW - timedelta(hours=12 * i + 1),
                download_mbps=10.0 if i < below else 90.0,
                contract_ok=i >= below,
            )
        )
    session.add_all(
        [
            measurement(
                device.id,
                main.id,
                measured_at=NOW - timedelta(days=8),
                download_mbps=10.0,
                contract_ok=False,
            ),
            measurement(
                device.id,
                main.id,
                measured_at=NOW - timedelta(hours=2),
                iface_type="wifi",
                download_mbps=10.0,
                contract_ok=None,
            ),
            measurement(
                device.id,
                main.id,
                measured_at=NOW - timedelta(hours=3),
                connection_status="offline",
                quality_status="offline",
                contract_ok=None,
            ),
        ]
    )
    await session.flush()
    return school, main


async def test_more_than_half_below_the_contract_over_7_days_is_a_sustained_mismatch(
    session: AsyncSession,
) -> None:
    await create_settings(session)
    _, mismatched = await school_below_contract(session, "VKO-C-060", below=6, total=10)
    _, kept = await school_below_contract(session, "VKO-C-040", below=4, total=10)

    # One main line per school; the reserve ones stay empty.
    assert await recompute_contract_compliance(session, now=NOW) == 2

    await session.refresh(mismatched)
    await session.refresh(kept)
    assert mismatched.compliance_below_pct == approx(60)
    assert mismatched.compliance_sustained_mismatch is True
    assert mismatched.compliance_window_days == 7
    assert kept.compliance_below_pct == approx(40)
    assert kept.compliance_sustained_mismatch is False
    reserve = await session.scalar(select(Line).where(Line.status == "reserve").limit(1))
    assert reserve is not None and reserve.compliance_checked_at is None


async def test_the_threshold_and_the_window_come_from_the_settings(
    session: AsyncSession,
) -> None:
    settings = await create_settings(session)
    _, line = await school_below_contract(session, "VKO-C-061", below=6, total=10)

    settings.contract_mismatch_threshold_pct = 70
    await session.flush()
    await recompute_contract_compliance(session, now=NOW)
    await session.refresh(line)
    assert (line.compliance_below_pct, line.compliance_sustained_mismatch) == (approx(60), False)

    # Over 3 days only the six measurements of the first 72 hours count, all below the contract.
    settings.contract_mismatch_window_days = 3
    await session.flush()
    await recompute_contract_compliance(session, now=NOW)
    await session.refresh(line)
    assert line.compliance_below_pct == approx(100)
    assert line.compliance_sustained_mismatch is True
    assert line.compliance_window_days == 3


async def test_the_card_and_the_analytics_show_the_recomputed_mismatch(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, main = await school_below_contract(session, "VKO-C-062", below=6, total=10)
    oblast = bearer(await create_user(session, "oblast"))
    analytics = {"level": "school", "school_id": school.id, "period": "week"}

    before = await api_client.get(f"/api/schools/{school.id}/lines", headers=oblast)
    report = await api_client.get("/api/analytics", params=analytics, headers=oblast)
    assert [line["contract_compliance"] for line in before.json()["items"]] == [None, None]
    assert report.json()["rows"][0]["sustained_mismatch_lines_count"] is None

    await recompute_contract_compliance(session, now=NOW)

    lines = (await api_client.get(f"/api/schools/{school.id}/lines", headers=oblast)).json()
    report = await api_client.get("/api/analytics", params=analytics, headers=oblast)
    assert lines["items"][0]["id"] == main.id
    assert lines["items"][0]["contract_compliance"] == {
        "sustained_mismatch": True,
        "below_contract_pct": approx(60),
        "window_days": 7,
    }
    assert lines["items"][1]["contract_compliance"] is None
    assert report.json()["rows"][0]["sustained_mismatch_lines_count"] == 1


def test_beat_runs_the_recompute() -> None:
    [entry] = [
        entry
        for entry in celery_app.conf.beat_schedule.values()
        if entry["task"] == RECOMPUTE_CONTRACT_COMPLIANCE
    ]
    assert entry["schedule"] > 0
    assert RECOMPUTE_CONTRACT_COMPLIANCE in celery_app.tasks


async def test_settings_hold_the_rule_of_the_decisions_by_default(session: AsyncSession) -> None:
    settings = await create_settings(session)
    assert (settings.contract_mismatch_threshold_pct, settings.contract_mismatch_window_days) == (
        50,
        7,
    )
