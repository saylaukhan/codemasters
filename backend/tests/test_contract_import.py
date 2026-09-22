"""T-61: a registry of contracts loaded from a CSV or XLSX file into the lines of schools.

ТЗ п. 14 keeps the contract on the line: the number, the date and the speeds it promises. Until
now they were typed by hand on the school card (T-35); the registry of the oblast is a table,
so the table is read. The rule of these tests: a preview writes nothing and leaves no record, an
import writes what the file has and one audit record with the counts, an empty cell changes
nothing, a row that cannot be applied is reported and skipped while the others go through.

The readers of the two formats are tested without the database: the CSV of Excel with its BOM
and «;», the CSV of cp1251, and an XLSX with shared strings — the writer of the exports uses
inline strings, so the shared ones are built here by hand.
"""

import base64
import csv
import zipfile
from datetime import date
from io import BytesIO, StringIO
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, ConnectionType, Line, Provider
from app.services.contract_import import parse_date, parse_speed
from app.services.exports.xlsx import xlsx_bytes
from app.services.spreadsheet import EXCEL_EPOCH, TableError, read_table
from tests.factories import bearer, create_school, create_settings, create_user
from tests.test_admin_incident_rules import ok, problem

PREVIEW = "/api/admin/contracts/import/preview"
IMPORT = "/api/admin/contracts/import"

HEADER = [
    "School ID",
    "Поставщик",
    "Идентификатор линии",
    "Тип подключения",
    "Номер договора",
    "Дата договора",
    "Download по договору, Мбит/с",
    "Upload по договору, Мбит/с",
]

SHARED_STRINGS_XLSX = {
    "[Content_Types].xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'  # noqa: E501
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'  # noqa: E501
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'  # noqa: E501
        "</Types>"
    ),
    "_rels/.rels": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'  # noqa: E501
        "</Relationships>"
    ),
    "xl/workbook.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Договоры" sheetId="1" r:id="rId7"/></sheets></workbook>'
    ),
    "xl/_rels/workbook.xml.rels": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'  # noqa: E501
        '<Relationship Id="rId8" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'  # noqa: E501
        "</Relationships>"
    ),
    "xl/sharedStrings.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">'  # noqa: E501
        "<si><t>School ID</t></si><si><t>Поставщик</t></si><si><t>Дата договора</t></si>"
        "<si><r><t>VKO-</t></r><r><t>UK-001</t></r></si></sst>"
    ),
    # The date is typed in Excel: a serial number with a date style, the provider is inline.
    "xl/worksheets/sheet1.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'  # noqa: E501
        '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="inlineStr"><is><t>Провайдер VKO-UK-001</t></is></c>'  # noqa: E501
        '<c r="C2" s="1"><v>46037</v></c></row>'
        '<row r="3"/>'
        "</sheetData></worksheet>"
    ),
}


def csv_file(rows: list[list[Any]], *, delimiter: str = ";", encoding: str = "utf-8-sig") -> bytes:
    """The file as Excel saves it: cells with the delimiter inside are quoted."""
    buffer = StringIO()
    csv.writer(buffer, delimiter=delimiter, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode(encoding)


def request_body(content: bytes, file_name: str = "contracts.csv") -> dict[str, str]:
    return {"file_name": file_name, "content": base64.b64encode(content).decode()}


async def line_of(session: AsyncSession, school_id: int, provider_name: str) -> Line:
    return (
        await session.scalars(
            select(Line)
            .join(Provider, Provider.id == Line.provider_id)
            .where(Line.school_id == school_id, Provider.name == provider_name)
        )
    ).one()


async def import_records(session: AsyncSession) -> list[tuple[Any, ...]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.entity_type, AuditLog.changes)
        .where(AuditLog.action == "import")
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows]


def test_csv_of_excel_and_xlsx_of_the_exports_are_read_alike() -> None:
    rows: list[list[Any]] = [
        HEADER[:2] + HEADER[6:7],
        ["VKO-UK-001", "Провайдер VKO-UK-001", 100],
        ["", "", ""],
        ["VKO-UK-002", "ТОО «Связь»", 50.5],
    ]
    expected = [
        ["School ID", "Поставщик", "Download по договору, Мбит/с"],
        ["VKO-UK-001", "Провайдер VKO-UK-001", "100"],
        ["VKO-UK-002", "ТОО «Связь»", "50.5"],
    ]

    assert read_table(csv_file(rows), "contracts.csv") == expected
    assert read_table(csv_file(rows, delimiter=","), "contracts.CSV") == expected
    assert read_table(csv_file(rows, encoding="cp1251"), "contracts.csv") == expected
    assert read_table(xlsx_bytes("Договоры", rows[0], rows[1:]), "contracts.xlsx") == expected


def test_shared_strings_and_dates_typed_in_excel_are_read() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, part in SHARED_STRINGS_XLSX.items():
            archive.writestr(name, part)

    table = read_table(buffer.getvalue(), "registry.xlsx")

    assert table == [
        ["School ID", "Поставщик", "Дата договора"],
        ["VKO-UK-001", "Провайдер VKO-UK-001", "46037"],
    ]
    assert parse_date("46037") == EXCEL_EPOCH.fromordinal(EXCEL_EPOCH.toordinal() + 46037)
    assert parse_date("46037") == date(2026, 1, 15)


def test_values_of_the_registry_are_read_as_people_type_them() -> None:
    assert parse_speed("100") == 100.0
    assert parse_speed("100,5 Мбит/с") == 100.5
    assert parse_date("15.01.2026") == parse_date("2026-01-15") == parse_date("15/01/2026")
    for bad in ("0", "много", "-5"):
        with pytest.raises(ValueError):
            parse_speed(bad)
    with pytest.raises(ValueError):
        parse_date("вчера")
    with pytest.raises(TableError):
        read_table(b"x", "contracts.txt")
    with pytest.raises(TableError):
        read_table(b"not a zip", "contracts.xlsx")


async def test_a_preview_reports_without_writing_and_the_import_applies_with_audit(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    other = await create_school(session, school_code="VKO-UK-002", with_point=False)
    session.add_all(
        [Provider(name="Новый провайдер"), ConnectionType(code="fiber", name="Оптоволокно")]
    )
    await session.flush()
    oblast = bearer(await create_user(session, "oblast"))
    rows: list[list[Any]] = [
        HEADER,
        # The main line of the school gets its contract; the School ID matches whatever the case.
        [
            "vko-uk-001",
            "Провайдер VKO-UK-001",
            "ACC-1",
            "Оптоволокно",
            "ДГ-1/2026",
            "15.01.2026",
            "100",
            "50,5",
        ],
        # A provider the school has no line of: a reserve line is created.
        [
            "VKO-UK-001",
            "Новый провайдер",
            "",
            "fiber",
            "ДГ-2/2026",
            "2026-02-01",
            "20 Мбит/с",
            "10",
        ],
        # Unknown provider and unknown school: reported, skipped.
        ["VKO-UK-002", "Неизвестный", "", "", "ДГ-3", "", "30", "30"],
        ["VKO-UK-999", "Провайдер VKO-UK-001", "", "", "ДГ-4", "", "30", "30"],
    ]
    body = request_body(csv_file(rows))

    preview = ok(await api_client.post(PREVIEW, json=body, headers=oblast))

    assert (preview["dry_run"], preview["rows_total"]) == (True, 4)
    assert (preview["created"], preview["updated"], preview["unchanged"], preview["failed"]) == (
        1,
        1,
        0,
        2,
    )
    assert [item["action"] for item in preview["items"]] == ["update", "create", "error", "error"]
    updated, created, unknown_provider, unknown_school = preview["items"]
    assert (updated["row"], updated["school_code"], updated["line_id"]) == (
        2,
        school.school_code,
        updated["line_id"],
    )
    assert updated["changes"]["contract_down_mbps"] == {"old": None, "new": 100.0}
    assert updated["changes"]["contract_up_mbps"] == {"old": None, "new": 50.5}
    assert updated["changes"]["contract_date"] == {"old": None, "new": "2026-01-15"}
    assert updated["changes"]["line_identifier"] == {"old": None, "new": "ACC-1"}
    assert created["changes"]["status"] == {"old": None, "new": "reserve"}
    assert created["line_id"] is None
    assert "Неизвестный" in unknown_provider["error"]
    assert "VKO-UK-999" in unknown_school["error"]
    # Nothing was written and nothing was logged.
    main = await line_of(session, school.id, f"Провайдер {school.school_code}")
    assert (main.contract_number, main.contract_down_mbps) == (None, None)
    assert len(list(await session.scalars(select(Line).where(Line.school_id == school.id)))) == 1
    assert await import_records(session) == []

    applied = ok(await api_client.post(IMPORT, json=body, headers=oblast))

    assert applied["dry_run"] is False
    assert [item["action"] for item in applied["items"]] == ["update", "create", "error", "error"]
    await session.refresh(main)
    assert (main.contract_number, main.contract_date) == ("ДГ-1/2026", date(2026, 1, 15))
    assert (main.contract_down_mbps, main.contract_up_mbps) == (100.0, 50.5)
    assert main.line_identifier == "ACC-1" and main.status == "main"
    fiber = (
        await session.scalars(select(ConnectionType).where(ConnectionType.code == "fiber"))
    ).one()
    assert main.connection_type_id == fiber.id
    reserve = await line_of(session, school.id, "Новый провайдер")
    assert applied["items"][1]["line_id"] == reserve.id
    assert (reserve.status, reserve.contract_number, reserve.contract_down_mbps) == (
        "reserve",
        "ДГ-2/2026",
        20.0,
    )
    assert reserve.connection_type_id == fiber.id
    # The lines of the other school are untouched: its row failed.
    assert list(
        await session.scalars(select(Line.contract_number).where(Line.school_id == other.id))
    ) == [None]
    assert await import_records(session) == [
        (
            "import",
            "line",
            {
                "file_name": {"old": None, "new": "contracts.csv"},
                "rows": {"old": None, "new": 4},
                "created": {"old": None, "new": 1},
                "updated": {"old": None, "new": 1},
                "failed": {"old": None, "new": 2},
            },
        )
    ]

    # The same file again changes nothing: the registry is already in the lines.
    again = ok(await api_client.post(PREVIEW, json=body, headers=oblast))
    assert [item["action"] for item in again["items"]] == [
        "unchanged",
        "unchanged",
        "error",
        "error",
    ]


async def test_an_empty_cell_changes_nothing_and_a_second_main_line_is_refused(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    await create_settings(session)
    school = await create_school(session)
    main = await line_of(session, school.id, f"Провайдер {school.school_code}")
    main.contract_number, main.contract_down_mbps, main.contract_up_mbps = "ДГ-0", 100.0, 50.0
    session.add(Provider(name="Второй"))
    await session.flush()
    admin = bearer(await create_user(session, "admin"))
    xlsx = xlsx_bytes(
        "Договоры",
        ["School ID", "Поставщик", "Статус линии", "Номер договора", "Download", "Upload"],
        [
            # The number stays, only the speeds change.
            [school.school_code, f"Провайдер {school.school_code}", "", "", 200, 100],
            # A second main line is what the panel refuses too (T-35).
            [school.school_code, "Второй", "основная", "ДГ-9", 10, 10],
        ],
    )

    report = ok(
        await api_client.post(IMPORT, json=request_body(xlsx, "registry.xlsx"), headers=admin)
    )

    assert [item["action"] for item in report["items"]] == ["update", "error"]
    assert report["items"][0]["changes"] == {
        "contract_down_mbps": {"old": 100.0, "new": 200.0},
        "contract_up_mbps": {"old": 50.0, "new": 100.0},
    }
    assert "основная" in report["items"][1]["error"]
    await session.refresh(main)
    assert (main.contract_number, main.contract_down_mbps, main.contract_up_mbps) == (
        "ДГ-0",
        200.0,
        100.0,
    )
    assert len(list(await session.scalars(select(Line).where(Line.school_id == school.id)))) == 1


async def test_a_file_without_the_required_columns_or_of_another_format_is_422(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    oblast = bearer(await create_user(session, "oblast"))

    no_provider = problem(
        await api_client.post(
            PREVIEW,
            json=request_body(csv_file([["School ID", "Договор"], ["VKO-UK-001", "x"]])),
            headers=oblast,
        ),
        422,
        "validation_error",
    )
    not_a_table = problem(
        await api_client.post(
            PREVIEW, json=request_body(b"hello", "contracts.docx"), headers=oblast
        ),
        422,
        "validation_error",
    )
    not_base64 = problem(
        await api_client.post(
            PREVIEW, json={"file_name": "contracts.csv", "content": "***"}, headers=oblast
        ),
        422,
        "validation_error",
    )
    empty = problem(
        await api_client.post(PREVIEW, json=request_body(b""), headers=oblast),
        422,
        "validation_error",
    )

    assert "Поставщик" in no_provider["errors"][0]["message"]
    assert [error["field"] for error in no_provider["errors"]] == ["content"]
    assert not_a_table["errors"][0]["message"] == "поддерживаются файлы CSV и XLSX"
    assert [error["field"] for error in not_base64["errors"]] == ["content"]
    assert "заголовка" in empty["errors"][0]["message"]


@pytest.mark.parametrize("role", ["school", "district", "provider", "oblast", "admin"])
async def test_only_the_roles_that_set_up_schools_import_contracts(
    session: AsyncSession, api_client: AsyncClient, role: str
) -> None:
    await create_settings(session)
    school = await create_school(session)
    provider_id = await session.scalar(select(Provider.id).order_by(Provider.id.desc()).limit(1))
    scope = {
        "school": {"school_id": school.id},
        "district": {"region_id": school.region_id},
        "provider": {"provider_id": provider_id},
    }.get(role, {})
    user = bearer(await create_user(session, role, **scope))
    body = request_body(
        csv_file([HEADER[:2], [school.school_code, f"Провайдер {school.school_code}"]])
    )

    responses = [
        await api_client.post(PREVIEW, json=body, headers=user),
        await api_client.post(IMPORT, json=body, headers=user),
    ]

    if role in ("oblast", "admin"):
        assert [response.status_code for response in responses] == [200, 200]
        assert [item["action"] for item in responses[1].json()["items"]] == ["unchanged"]
        return
    for response in responses:
        problem(response, 403, "forbidden")
