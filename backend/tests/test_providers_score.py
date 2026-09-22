"""T-68: the score of a provider, its card, the act and the scope (ТЗ п. 14, п. 19; ADR-008).

Two districts with one school each, as in ``test_overview``, and one provider per district: the
schools of the two are never mixed, so a district row and a provider row must hold exactly one
of them. Measurements are put straight into the database with the evaluation the server of T-18
would have written — ``contract_ok`` and ``thresholds_snapshot`` — because that snapshot, not
the profile of today, is what the claim act argues from (ТЗ п. 11).

The moment of the request is fixed with ``period_to``: statuses and availability depend on the
working hours (ADR-014), and a test must not depend on when it runs.
"""

import uuid
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    Incident,
    IncidentEvent,
    Line,
    Measurement,
    MonitoringPoint,
    School,
    SystemSettings,
)
from app.services.provider_act import provider_act
from tests.factories import bearer, create_settings, create_user
from tests.test_incidents import an_incident
from tests.test_overview import WORKDAY, get, school_with_series

SCORE = "/api/providers/score"
DAY = {"period": "custom", "period_from": (WORKDAY - timedelta(days=1)).isoformat()}
HOUR = timedelta(hours=1)

# Thresholds of the global profile the migration of T-17 creates, as they were snapshotted into
# the measurements below together with the contract of the line.
PROFILE = {
    "profile_id": 1,
    "profile_scope": "global",
    "download_min_mbps": 20.0,
    "upload_min_mbps": 20.0,
    "ping_max_ms": 100.0,
    "jitter_max_ms": 30.0,
    "packet_loss_max_pct": 2.0,
    "unstable_deviation_pct": 30.0,
    "rates_line": True,
}
CONTRACT_DOWN = 50.0
CONTRACT_UP = 25.0


def snapshot(**overrides: Any) -> dict[str, Any]:
    """``thresholds_snapshot`` of a measurement: the thresholds and the contract of its moment."""
    return {
        **PROFILE,
        "contract_down_mbps": CONTRACT_DOWN,
        "contract_up_mbps": CONTRACT_UP,
        **overrides,
    }


async def line_of(session: AsyncSession, school: School) -> Line:
    return (await session.scalars(select(Line).where(Line.school_id == school.id))).one()


async def a_school(
    session: AsyncSession,
    code: str,
    *,
    lon: float,
    measurements: int,
    below: int,
    contract: tuple[float, float] = (CONTRACT_DOWN, CONTRACT_UP),
) -> School:
    """School of its own district and provider, with a contract on its main line and
    ``measurements`` measurements of the last day, ``below`` of them under the contract."""
    school = await school_with_series(session, code, [], lon=lon)
    line = await line_of(session, school)
    line.contract_down_mbps, line.contract_up_mbps = contract
    await session.flush()
    device_id = await device_of(session, school)
    for index in range(measurements):
        kept = index >= below
        session.add(
            Measurement(
                measurement_uuid=uuid.uuid4(),
                measured_at=WORKDAY - (index + 1) * HOUR,
                device_id=device_id,
                line_id=line.id,
                connection_status="online",
                iface_type="ethernet",
                download_mbps=CONTRACT_DOWN + 10 if kept else 12.0,
                upload_mbps=CONTRACT_UP + 5 if kept else 8.0,
                ping_ms=20.0,
                quality_status="normal" if kept else "critical",
                thresholds_snapshot=snapshot(),
                contract_ok=kept,
            )
        )
    await session.flush()
    return school


async def device_of(session: AsyncSession, school: School) -> int:
    """The registered computer of the school: ``school_with_series`` leaves exactly one."""
    device_id = await session.scalar(
        select(Device.id)
        .join(MonitoringPoint, MonitoringPoint.id == Device.monitoring_point_id)
        .where(MonitoringPoint.school_id == school.id)
    )
    assert device_id is not None
    return device_id


async def two_providers(session: AsyncSession) -> tuple[School, School]:
    """District A — half of its measurements below the contract; district B — none of them."""
    await create_settings(session)
    school_a = await a_school(session, "VKO-A-001", lon=82.6, measurements=4, below=2)
    school_b = await a_school(session, "VKO-B-001", lon=82.7, measurements=4, below=0)
    return school_a, school_b


async def provider_of(session: AsyncSession, school: School) -> int:
    provider_id = await session.scalar(select(Line.provider_id).where(Line.school_id == school.id))
    assert provider_id is not None
    return provider_id


async def slow_answer(session: AsyncSession, school: School) -> None:
    """An incident of the school answered twelve hours later: three norms of reaction late."""
    incident = await an_incident(
        session, school, status="in_progress", started_at=WORKDAY - 20 * HOUR
    )
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            kind="status_change",
            from_status="new",
            to_status="in_progress",
            created_at=WORKDAY - 8 * HOUR,
        )
    )
    await session.flush()


async def test_a_district_sees_only_its_own_providers(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_providers(session)
    district = bearer(await create_user(session, "district", region_id=school_a.region_id))

    report = await get(api_client, SCORE, district, **DAY)

    assert [row["name"] for row in report["rows"]] == ["Провайдер VKO-A-001"]
    [row] = report["rows"]
    assert (row["schools_count"], row["lines_count"], row["measurements_count"]) == (1, 1, 4)
    assert row["below_contract_pct"] == 50.0
    # The provider of the other district is not a row, and his card is not even a 200.
    other = await provider_of(session, school_b)
    hidden = await api_client.get(
        f"/api/providers/{other}/score",
        headers=district,
        params={"period_to": WORKDAY.isoformat(), **DAY},
    )
    assert hidden.status_code == 404, hidden.text


async def test_a_provider_sees_only_itself(session: AsyncSession, api_client: AsyncClient) -> None:
    _, school_b = await two_providers(session)
    provider_b = await provider_of(session, school_b)
    provider = bearer(await create_user(session, "provider", provider_id=provider_b))

    report = await get(api_client, SCORE, provider, **DAY)
    card = await get(api_client, f"/api/providers/{provider_b}/score", provider, **DAY)

    assert [row["id"] for row in report["rows"]] == [provider_b]
    assert card["provider"]["id"] == provider_b
    assert [school["name"] for school in card["schools"]] == ["Школа VKO-B-001"]


async def test_the_weights_of_the_settings_decide_the_order_of_two_providers(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, school_b = await two_providers(session)
    # Provider A is slow against the contract, provider B is slow to answer an incident.
    await slow_answer(session, school_b)
    oblast = bearer(await create_user(session, "oblast"))

    with_defaults = await get(api_client, SCORE, oblast, **DAY)
    by_score = {row["name"]: row["score"] for row in with_defaults["rows"]}
    assert by_score["Провайдер VKO-A-001"] > by_score["Провайдер VKO-B-001"]
    assert with_defaults["weights"]["below_contract"] == 40
    [row_b] = [
        row for row in with_defaults["rows"] if row["id"] != await provider_of(session, school_a)
    ]
    assert (row_b["incidents_opened"], row_b["reaction_median_s"]) == (1, 12 * 3600)

    # The share below the contract now weighs everything: the same numbers, the other order.
    settings = await session.get(SystemSettings, 1)
    assert settings is not None
    settings.provider_score_weight_below_contract = 100
    await session.flush()

    reweighted = await get(api_client, SCORE, oblast, **DAY)
    flipped = {row["name"]: row["score"] for row in reweighted["rows"]}
    assert flipped["Провайдер VKO-A-001"] < flipped["Провайдер VKO-B-001"]
    assert reweighted["weights"]["below_contract"] == 100


async def test_the_card_lists_the_lines_whose_contract_is_below_the_norm(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    # The contract itself promises 10 Mbit/s, less than the 20 of the global profile: «не
    # претензия» — the school needs a new contract, not an appeal (§6.3).
    school = await a_school(
        session, "VKO-C-001", lon=82.8, measurements=2, below=1, contract=(10.0, 10.0)
    )
    provider_id = await provider_of(session, school)
    oblast = bearer(await create_user(session, "oblast"))

    card = await get(api_client, f"/api/providers/{provider_id}/score", oblast, **DAY)

    assert card["provider"]["lines_below_norm_count"] == 1
    [line] = card["lines_below_norm"]
    assert (line["contract_down_mbps"], line["download_min_mbps"]) == (10.0, 20.0)
    assert line["school_name"] == "Школа VKO-C-001"


async def test_the_act_argues_from_the_snapshot_of_a_measurement(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_providers(session)
    line = await line_of(session, school_a)
    # The contract is renegotiated today and the profile is raised: the act must still show the
    # numbers the measurement was judged by (ТЗ п. 11, ADR-004).
    line.contract_down_mbps = 500.0
    await session.flush()
    provider_id = await provider_of(session, school_a)
    oblast = bearer(await create_user(session, "oblast"))

    answer = await api_client.get(
        f"/api/providers/{provider_id}/act",
        headers=oblast,
        params={"period_to": WORKDAY.isoformat(), **DAY},
    )

    assert answer.status_code == 200, answer.text
    assert answer.headers["content-type"] == "application/pdf"
    assert answer.content.startswith(b"%PDF-")
    # The PDF is drawn with the fonts of T-32; the numbers of the rows are checked on the
    # document the drawing is given, which is where they come from.
    document = await provider_act(
        session,
        provider_id,
        period="custom",
        period_from=WORKDAY - timedelta(days=1),
        period_to=WORKDAY,
        now=WORKDAY,
    )
    assert document.below_contract_count == 2
    assert {row.contract_down_mbps for row in document.rows} == {CONTRACT_DOWN}
    assert {row.download_min_mbps for row in document.rows} == {20.0}


async def test_an_incident_without_an_answer_has_no_reaction_time(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    school_a, _ = await two_providers(session)
    await an_incident(session, school_a, started_at=WORKDAY - 3 * HOUR)
    oblast = bearer(await create_user(session, "oblast"))

    report = await get(api_client, SCORE, oblast, **DAY)

    [row] = [row for row in report["rows"] if row["name"] == "Провайдер VKO-A-001"]
    assert (row["incidents_opened"], row["incidents_closed"]) == (1, 0)
    assert row["reaction_median_s"] is None
    assert (
        await session.scalar(select(Incident.provider_id).where(Incident.school_id == school_a.id))
        == row["id"]
    )
