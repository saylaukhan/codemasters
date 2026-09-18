"""T-32: PDF report of a school — header, KPI, downtime from ``outages``, measurements, scope.

The school of ``test_exports``: three measurements on 14.09 local time (normal, critical,
unstable) and one on 15.09 outside the period. The text is read as a viewer reads it: glyph ids
of the pages mapped back to letters through the ToUnicode map of the embedded font.
"""

import re
import zlib
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, MonitoringPoint, Outage
from app.services.exports import build_pending_export
from tests.factories import bearer, create_settings, create_user
from tests.test_exports import PERIOD_FROM, download, measured_school, request_body

STREAM = re.compile(rb"<< /Length (\d+) /Filter /FlateDecode[^>]*>>\nstream\n")
BFCHAR = re.compile(rb"beginbfchar\n(.*?)\nendbfchar", re.S)
GLYPHS = re.compile(rb"<([0-9A-F]+)> Tj")


def pdf_streams(content: bytes) -> list[bytes]:
    return [
        zlib.decompress(content[match.end() : match.end() + int(match.group(1))])
        for match in STREAM.finditer(content)
    ]


def pdf_text(content: bytes) -> str:
    """Every text run of the pages, one per line, NBSP as a space."""
    streams = pdf_streams(content)
    letters: dict[str, str] = {}
    for data in streams:
        for block in BFCHAR.findall(data):
            for line in block.decode().splitlines():
                glyph, code = line.strip("<>").split("> <")
                letters[glyph] = bytes.fromhex(code).decode("utf-16-be")
    runs = []
    for data in streams:
        for glyphs in GLYPHS.findall(data):
            text = glyphs.decode()
            runs.append("".join(letters[text[i : i + 4]] for i in range(0, len(text), 4)))
    return "\n".join(runs).replace("\u00a0", " ")


async def with_outages(session: AsyncSession, device: Device) -> None:
    """Two overlapping reports (10:00–10:30 and 10:20–11:00) and one more (15:00–15:15)."""
    line_id = await session.scalar(
        select(MonitoringPoint.line_id).where(MonitoringPoint.id == device.monitoring_point_id)
    )
    assert line_id is not None
    for start, minutes in [(10 * 60, 30), (10 * 60 + 20, 40), (15 * 60, 15)]:
        started_at = PERIOD_FROM + timedelta(minutes=start)
        session.add(
            Outage(
                device_id=device.id,
                line_id=line_id,
                started_at=started_at,
                ended_at=started_at + timedelta(minutes=minutes),
            )
        )
    await session.flush()


async def test_the_report_names_the_school_and_counts_its_downtime(
    session: AsyncSession, api_client: AsyncClient, export_queue: list[int]
) -> None:
    await create_settings(session)
    school, device = await measured_school(session, "VKO-PDF-001")
    await with_outages(session, device)
    headers = bearer(await create_user(session, "oblast"))

    created = await api_client.post(
        "/api/exports",
        json=request_body(mode="school_report", format="pdf", school_ids=[school.id]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    job = created.json()
    # Every PDF is built by the Celery worker (T-33).
    assert job["status"] == "pending"
    assert export_queue == [job["id"]]
    assert await build_pending_export(session, job["id"], now=datetime.now(UTC)) == "ready"
    listed = (await api_client.get("/api/exports", headers=headers)).json()["items"]
    response = await download(api_client, headers, job["id"])
    text = pdf_text(response.content)

    assert listed[0]["rows_count"] == 3
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="report_VKO-PDF-001_2026-09-14_2026-09-14.pdf"'
    )
    assert response.content.startswith(b"%PDF-1.7")
    assert b"/FontFile2" in response.content
    assert school.full_name in text
    assert "School ID VKO-PDF-001" in text
    assert "Период: 14.09.2026 — 14.09.2026" in text
    # KPI of the main line: two of the three measurements are problems.
    assert "66,7%" in text
    assert "2 из 3 замеров" in text
    # The overlapping reports are one downtime: 10:00–11:00 and 15:00–15:15.
    assert "Простоев: 2, суммарно 1 ч 15 мин." in text
    assert "14.09.2026 10:00\n14.09.2026 11:00\n1 ч" in text
    assert {"Норма", "Критично", "Нестабильно"} <= set(text.splitlines())
    assert "PC-VKO-PDF-001\nКаб. 12\nОсновная\n95,5\n40,0\n13\n2\n0,0\nНорма" in text


async def test_a_school_outside_the_scope_gets_no_report(
    session: AsyncSession, api_client: AsyncClient, export_queue: list[int]
) -> None:
    await create_settings(session)
    own, _ = await measured_school(session, "VKO-PDF-001")
    other, _ = await measured_school(session, "VKO-PDF-002")
    headers = bearer(await create_user(session, "school", school_id=own.id))

    foreign = await api_client.post(
        "/api/exports",
        json=request_body(mode="school_report", format="pdf", school_ids=[other.id]),
        headers=headers,
    )
    own_report = await api_client.post(
        "/api/exports",
        json=request_body(mode="school_report", format="pdf", school_ids=[own.id]),
        headers=headers,
    )

    assert foreign.status_code == 422, foreign.text
    assert [error["field"] for error in foreign.json()["errors"]] == ["school_ids"]
    assert own_report.status_code == 201, own_report.text
    await build_pending_export(session, own_report.json()["id"], now=datetime.now(UTC))
    text = pdf_text((await download(api_client, headers, own_report.json()["id"])).content)
    assert own.full_name in text
    assert other.full_name not in text
