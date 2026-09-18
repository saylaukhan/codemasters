"""T-30: raw export of measurements — XLSX, CSV and JSON, filters, columns and the scope."""

import csv
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Export, Line, Measurement, School
from app.schemas.exports import MIN_EXPORT_COLUMNS
from tests.factories import (
    bearer,
    create_school,
    create_settings,
    create_user,
    primary_point,
    register_device,
)

ALMATY = ZoneInfo("Asia/Almaty")
PERIOD_FROM = datetime(2026, 9, 14, tzinfo=ALMATY)
PERIOD_TO = datetime(2026, 9, 15, tzinfo=ALMATY)
HEADER = [
    "Школа",
    "Компьютер",
    "Кабинет",
    "Дата",
    "Время",
    "Download, Мбит/с",
    "Upload, Мбит/с",
    "Ping, мс",
    "Jitter, мс",
    "Packet Loss, %",
    "Статус",
]
LABELS = {"normal": "Норма", "unstable": "Нестабильно", "critical": "Критично"}
SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


async def measured_school(session: AsyncSession, code: str) -> tuple[School, Device]:
    """School with one computer in «Каб. 12» and three measurements on 14.09 local time; one more
    measurement a day later lies outside the period."""
    school = await create_school(session, school_code=code, room="Каб. 12")
    point = await primary_point(session, school)
    device, _ = await register_device(session, point, device_uid=f"UID-{code}")
    device.hostname = f"PC-{code}"
    line = await session.get_one(Line, point.line_id)
    for hour, status, download in [
        (9, "normal", 95.5),
        (13, "critical", 4.25),
        (17, "unstable", 30.0),
        (33, "normal", 90.0),
    ]:
        session.add(
            Measurement(
                measurement_uuid=uuid.uuid4(),
                measured_at=PERIOD_FROM + timedelta(hours=hour, minutes=5, seconds=7),
                device_id=device.id,
                line_id=line.id,
                connection_status="online",
                iface_type="ethernet",
                download_mbps=download,
                upload_mbps=40.0,
                ping_ms=12.5,
                jitter_ms=1.5,
                packet_loss_pct=0.0,
                quality_status=status,
                external_ip="203.0.113.7",
            )
        )
    await session.flush()
    return school, device


def request_body(**changes: Any) -> dict[str, Any]:
    return {
        "mode": "raw",
        "format": "xlsx",
        "period_from": PERIOD_FROM.isoformat(),
        "period_to": PERIOD_TO.isoformat(),
    } | changes


async def export(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    created = await client.post("/api/exports", json=request_body(**changes), headers=headers)
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "ready"
    return job


async def download(client: AsyncClient, headers: dict[str, str], export_id: int) -> Any:
    response = await client.get(f"/api/exports/{export_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response


def xlsx_rows(content: bytes) -> list[list[str]]:
    """Cells of the first sheet as text, row by row."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert "xl/workbook.xml" in archive.namelist()
    rows = []
    for row in sheet.iter(f"{SHEET}row"):
        rows.append(
            ["".join(cell.itertext()) for cell in row.iter(f"{SHEET}c")],
        )
    return rows


async def test_xlsx_has_the_columns_of_tz_p9_and_the_rows_of_the_database(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, device = await measured_school(session, "VKO-EX-001")
    headers = bearer(await create_user(session, "oblast"))

    job = await export(api_client, headers)
    response = await download(api_client, headers, job["id"])

    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="measurements_2026-09-14_2026-09-14.xlsx"'
    )
    measurements = (
        await session.scalars(
            select(Measurement)
            .where(
                Measurement.device_id == device.id,
                Measurement.measured_at >= PERIOD_FROM,
                Measurement.measured_at < PERIOD_TO,
            )
            .order_by(Measurement.measured_at)
        )
    ).all()
    expected = [
        [
            school.full_name,
            "PC-VKO-EX-001",
            "Каб. 12",
            m.measured_at.astimezone(ALMATY).strftime("%d.%m.%Y"),
            m.measured_at.astimezone(ALMATY).strftime("%H:%M:%S"),
            repr(m.download_mbps),
            repr(m.upload_mbps),
            repr(m.ping_ms),
            repr(m.jitter_ms),
            repr(m.packet_loss_pct),
            LABELS[m.quality_status or ""],
        ]
        for m in measurements
    ]
    assert job["rows_count"] == len(measurements) == 3
    assert xlsx_rows(response.content) == [HEADER, *expected]
    assert expected[0][3:5] == ["14.09.2026", "09:05:07"]


async def test_csv_and_json_carry_the_same_records_and_the_chosen_columns(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    await measured_school(session, "VKO-EX-001")
    headers = bearer(await create_user(session, "oblast"))
    columns = [*MIN_EXPORT_COLUMNS, "school_code", "iface_type", "external_ip"]

    csv_job = await export(api_client, headers, format="csv", columns=columns)
    json_job = await export(api_client, headers, format="json", columns=columns)
    csv_file = (await download(api_client, headers, csv_job["id"])).content
    json_file = await download(api_client, headers, json_job["id"])

    assert csv_file.startswith("﻿".encode())
    csv_rows = list(csv.reader(io.StringIO(csv_file.decode("utf-8-sig")), delimiter=";"))
    assert csv_rows[0] == [*HEADER, "School ID", "Интерфейс", "Внешний IP"]
    assert csv_rows[1] == [
        "Школа VKO-EX-001",
        "PC-VKO-EX-001",
        "Каб. 12",
        "14.09.2026",
        "09:05:07",
        "95,5",
        "40,0",
        "12,5",
        "1,5",
        "0,0",
        "Норма",
        "VKO-EX-001",
        "Ethernet",
        "203.0.113.7",
    ]
    records = json_file.json()
    assert json_file.headers["content-type"] == "application/json"
    assert [list(record) for record in records] == [columns] * 3
    assert records[1] == {
        "school_name": "Школа VKO-EX-001",
        "hostname": "PC-VKO-EX-001",
        "room": "Каб. 12",
        "date": "2026-09-14",
        "time": "13:05:07",
        "download_mbps": 4.25,
        "upload_mbps": 40.0,
        "ping_ms": 12.5,
        "jitter_ms": 1.5,
        "packet_loss_pct": 0.0,
        "quality_status": "critical",
        "school_code": "VKO-EX-001",
        "iface_type": "ethernet",
        "external_ip": "203.0.113.7",
    }
    assert json.loads(json_file.content)[0]["time"] == "09:05:07"


async def test_filters_by_school_computer_and_status(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    first, first_device = await measured_school(session, "VKO-EX-001")
    second, _ = await measured_school(session, "VKO-EX-002")
    headers = bearer(await create_user(session, "oblast"))

    everything = await export(api_client, headers, format="json")
    of_second = await export(api_client, headers, format="json", school_ids=[second.id])
    problems = await export(
        api_client,
        headers,
        format="json",
        school_ids=[first.id],
        device_ids=[first_device.id],
        statuses=["critical", "unstable"],
    )

    assert everything["rows_count"] == 6
    rows = (await download(api_client, headers, of_second["id"])).json()
    assert {row["school_name"] for row in rows} == {second.full_name}
    rows = (await download(api_client, headers, problems["id"])).json()
    assert [row["quality_status"] for row in rows] == ["critical", "unstable"]


async def test_school_role_cannot_export_another_school(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    own, _ = await measured_school(session, "VKO-EX-001")
    other, other_device = await measured_school(session, "VKO-EX-002")
    headers = bearer(await create_user(session, "school", school_id=own.id))

    foreign_school = await api_client.post(
        "/api/exports", json=request_body(school_ids=[other.id]), headers=headers
    )
    foreign_device = await api_client.post(
        "/api/exports", json=request_body(device_ids=[other_device.id]), headers=headers
    )
    job = await export(api_client, headers, format="json")

    for response, field in [(foreign_school, "school_ids"), (foreign_device, "device_ids")]:
        assert response.status_code == 422, response.text
        assert [error["field"] for error in response.json()["errors"]] == [field]
    rows = (await download(api_client, headers, job["id"])).json()
    assert job["rows_count"] == 3
    assert {row["school_name"] for row in rows} == {own.full_name}


async def test_the_file_is_served_only_to_its_owner_until_it_expires(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    await measured_school(session, "VKO-EX-001")
    owner = bearer(await create_user(session, "oblast"))
    stranger = bearer(await create_user(session, "admin"))

    job = await export(api_client, owner)
    foreign = await api_client.get(f"/api/exports/{job['id']}", headers=stranger)
    expires_at = datetime.fromisoformat(job["expires_at"])
    await session.execute(
        update(Export)
        .where(Export.id == job["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    expired = await api_client.get(f"/api/exports/{job['id']}", headers=owner)

    assert timedelta(days=6, hours=23) < expires_at - datetime.now(UTC) <= timedelta(days=7)
    assert foreign.status_code == 404
    assert expired.status_code == 404


async def test_the_school_report_is_a_later_task(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school, _ = await measured_school(session, "VKO-EX-001")
    headers = bearer(await create_user(session, "oblast"))

    response = await api_client.post(
        "/api/exports",
        json=request_body(mode="school_report", format="pdf", school_ids=[school.id]),
        headers=headers,
    )

    assert response.status_code == 501
    assert "T-32" in response.json()["detail"]
