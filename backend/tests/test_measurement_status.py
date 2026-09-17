"""T-18: status of a measurement, snapshot of the thresholds, contract_ok (ТЗ п. 11, п. 13).

The table of conditions is plan.md §6 and needs no database: ``evaluate`` judges one measurement
against one profile. The database tests are about the chain the profile is taken from — line,
district, global (ADR-004) — and about the promise that a later change of the profile never
rewrites a stored snapshot.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Line, School, ThresholdProfile
from app.schemas.agent import MeasurementCreate
from app.services.status import LineRules, evaluate, line_rules
from tests.factories import create_school, primary_point, register_device
from tests.test_agent_measurements import MEASUREMENTS, measurement, stored
from tests.test_agent_register import as_device

# Base thresholds of ТЗ п. 11, as the migration of T-17 creates the global profile.
BASE_THRESHOLDS = {
    "download_min_mbps": 20.0,
    "upload_min_mbps": 20.0,
    "ping_max_ms": 100.0,
    "jitter_max_ms": 30.0,
    "packet_loss_max_pct": 2.0,
    "unstable_deviation_pct": 30.0,
}

# A measurement well inside the thresholds; every case below spoils one value or two.
GOOD = {
    "connection_status": "online",
    "download_mbps": 94.5,
    "upload_mbps": 88.1,
    "ping_ms": 12.0,
    "jitter_ms": 1.5,
    "packet_loss_pct": 0.0,
}

# Conditions of plan.md §6: what is measured → which status it gets with the base thresholds.
CASES = [
    ("everything inside the thresholds", {}, "normal"),
    # One metric past its limit by exactly the allowed share is still «Нестабильно».
    ("ping 130 ms against 100 — thirty percent", {"ping_ms": 130.0}, "unstable"),
    ("download 14 against 20 — thirty percent", {"download_mbps": 14.0}, "unstable"),
    ("loss 2.5 % against 2 — a quarter", {"packet_loss_pct": 2.5}, "unstable"),
    # A deviation larger than the allowed share is «Критично» even alone.
    ("ping 131 ms against 100 — past thirty", {"ping_ms": 131.0}, "critical"),
    ("download 13.9 against 20 — past thirty", {"download_mbps": 13.9}, "critical"),
    # Several metrics are «Критично» however small each deviation is.
    ("ping and jitter both slightly past", {"ping_ms": 110.0, "jitter_ms": 33.0}, "critical"),
    # No connection beats any number (ТЗ п. 13).
    (
        "no connection at all",
        {
            "connection_status": "offline",
            "download_mbps": None,
            "upload_mbps": None,
            "ping_ms": None,
            "jitter_ms": None,
            "packet_loss_pct": None,
        },
        "offline",
    ),
    # A metric the agent did not measure is «нет данных», not a fault of the line.
    ("upload not measured", {"upload_mbps": None}, "normal"),
]


def profile(**values: float) -> ThresholdProfile:
    """Global profile with the base thresholds of ТЗ п. 11 unless the test changes one."""
    return ThresholdProfile(id=1, scope="global", is_active=True, **(BASE_THRESHOLDS | values))


def rules(**contract: float | None) -> LineRules:
    """Thresholds of a line whose contract promises nothing unless the test says otherwise."""
    return LineRules(
        profile=profile(),
        contract_down_mbps=contract.get("down"),
        contract_up_mbps=contract.get("up"),
    )


def measured(**values: Any) -> MeasurementCreate:
    """One measurement as the agent sends it: raw numbers, no status of its own (ADR-004)."""
    return MeasurementCreate.model_validate(measurement() | GOOD | values)


@pytest.mark.parametrize(("case", "values", "expected"), CASES, ids=[case for case, _, _ in CASES])
def test_status_of_a_measurement_follows_the_thresholds(
    case: str, values: dict[str, Any], expected: str
) -> None:
    verdict = evaluate(measured(**values), rules())

    assert verdict.quality_status == expected, case
    # The numbers it was judged by travel with the record (ТЗ п. 11).
    assert verdict.thresholds_snapshot["ping_max_ms"] == 100.0
    assert verdict.thresholds_snapshot["profile_scope"] == "global"


def test_the_breach_is_written_out_with_its_deviation() -> None:
    verdict = evaluate(measured(ping_ms=130.0), rules())

    assert verdict.thresholds_snapshot["breaches"] == [
        {"metric": "ping_ms", "value": 130.0, "limit": 100.0, "deviation_pct": 30.0}
    ]


def test_a_zero_limit_has_no_percent_so_any_breach_of_it_is_critical() -> None:
    """«Никаких потерь» cannot be exceeded by a share: 0.1 % against 0 is «Критично»."""
    strict = LineRules(
        profile=profile(packet_loss_max_pct=0.0), contract_down_mbps=None, contract_up_mbps=None
    )

    verdict = evaluate(measured(packet_loss_pct=0.1), strict)

    assert verdict.quality_status == "critical"
    assert verdict.thresholds_snapshot["breaches"][0]["deviation_pct"] is None


def test_wifi_is_judged_but_marked_as_not_rating_the_line() -> None:
    verdict = evaluate(measured(iface_type="wifi", ping_ms=300.0), rules(down=50.0))

    assert verdict.quality_status == "critical"
    assert verdict.thresholds_snapshot["rates_line"] is False
    # The air says nothing about what the provider promised (ADR-012).
    assert verdict.contract_ok is None


@pytest.mark.parametrize(
    ("download", "contract", "expected"),
    [(94.5, {"down": 50.0}, True), (30.0, {"down": 50.0}, False), (94.5, {}, None)],
)
def test_contract_is_compared_with_the_fact_separately_from_the_thresholds(
    download: float, contract: dict[str, float], expected: bool | None
) -> None:
    verdict = evaluate(measured(download_mbps=download), rules(**contract))

    # Below the contract but inside the thresholds: two different questions (ТЗ п. 14).
    assert verdict.quality_status == "normal"
    assert verdict.contract_ok is expected


async def line_of(session: AsyncSession, school: School) -> Line:
    return (await session.scalars(select(Line).where(Line.school_id == school.id))).one()


async def test_global_profile_answers_when_there_is_nothing_more_specific(
    session: AsyncSession,
) -> None:
    """The profile the migration of T-17 creates is the floor of the chain (ТЗ п. 11)."""
    school = await create_school(session)

    chosen = await line_rules(session, (await line_of(session, school)).id)

    assert chosen.profile.scope == "global"
    assert chosen.profile.download_min_mbps == BASE_THRESHOLDS["download_min_mbps"]


async def test_district_profile_wins_over_the_global_one(session: AsyncSession) -> None:
    school = await create_school(session)
    session.add(
        ThresholdProfile(
            scope="district",
            region_id=school.region_id,
            **(BASE_THRESHOLDS | {"ping_max_ms": 60.0}),
        )
    )
    await session.flush()

    chosen = await line_rules(session, (await line_of(session, school)).id)

    assert chosen.profile.scope == "district"
    assert chosen.profile.ping_max_ms == 60.0


async def test_profile_of_the_line_wins_over_the_district_and_the_global_one(
    session: AsyncSession,
) -> None:
    school = await create_school(session)
    line = await line_of(session, school)
    session.add_all(
        [
            ThresholdProfile(
                scope="district",
                region_id=school.region_id,
                **(BASE_THRESHOLDS | {"ping_max_ms": 60.0}),
            ),
            ThresholdProfile(
                scope="line", line_id=line.id, **(BASE_THRESHOLDS | {"ping_max_ms": 40.0})
            ),
        ]
    )
    await session.flush()

    chosen = await line_rules(session, line.id)

    assert chosen.profile.scope == "line"
    assert chosen.profile.ping_max_ms == 40.0


async def test_an_inactive_profile_does_not_count(session: AsyncSession) -> None:
    school = await create_school(session)
    session.add(
        ThresholdProfile(
            scope="district",
            region_id=school.region_id,
            is_active=False,
            **(BASE_THRESHOLDS | {"ping_max_ms": 60.0}),
        )
    )
    await session.flush()

    chosen = await line_rules(session, (await line_of(session, school)).id)

    assert chosen.profile.scope == "global"


async def test_received_measurement_is_evaluated_at_once(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school = await create_school(session)
    line = await line_of(session, school)
    line.contract_down_mbps = 100.0
    line.contract_up_mbps = 100.0
    _, token = await register_device(session, await primary_point(session, school))
    body = measurement(download_mbps=94.5, upload_mbps=88.1, ping_ms=130.0)

    response = await api_client.post(MEASUREMENTS, json=body, headers=as_device(token))

    assert response.status_code == 201, response.text
    saved = await stored(session, body["measurement_uuid"])
    assert saved.quality_status == "unstable"
    # Below the contract, inside the thresholds: the two answers are independent (ТЗ п. 14).
    assert saved.contract_ok is False
    assert saved.thresholds_snapshot is not None
    assert saved.thresholds_snapshot["ping_max_ms"] == 100.0
    assert saved.thresholds_snapshot["contract_down_mbps"] == 100.0
    assert saved.thresholds_snapshot["rates_line"] is True


async def test_changing_the_profile_leaves_stored_snapshots_alone(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """A new threshold works from the next measurement on; history keeps its own numbers."""
    school = await create_school(session)
    _, token = await register_device(session, await primary_point(session, school))
    before = measurement(ping_ms=130.0)
    assert (
        await api_client.post(MEASUREMENTS, json=before, headers=as_device(token))
    ).status_code == 201

    await session.execute(
        update(ThresholdProfile).where(ThresholdProfile.scope == "global").values(ping_max_ms=200.0)
    )
    after = measurement(ping_ms=130.0)
    assert (
        await api_client.post(MEASUREMENTS, json=after, headers=as_device(token))
    ).status_code == 201

    old = await stored(session, before["measurement_uuid"])
    new = await stored(session, after["measurement_uuid"])
    assert old.thresholds_snapshot is not None and old.thresholds_snapshot["ping_max_ms"] == 100.0
    assert old.quality_status == "unstable"
    assert new.thresholds_snapshot is not None and new.thresholds_snapshot["ping_max_ms"] == 200.0
    assert new.quality_status == "normal"
