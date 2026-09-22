"""Import of a contract registry from a CSV or XLSX file into the lines of schools (T-61;
ТЗ п. 14, п. 20).

The registry of the oblast is a table: School ID, the provider, the number and the date of the
contract, the speeds it promises, and, when the registry has them, the identifier of the line,
its role and its technology. A row finds the line by the School ID and the provider — and by
the identifier when the file has one; a school without such a line gets a new one, main when
the school has no main line and reserve otherwise. A found line takes the values of the columns
the file has; an empty cell changes nothing, so a registry without dates never clears them, and
the role of an existing line is never changed by a file: the main line is chosen in the panel
(T-35). What the import writes is what the panel writes by hand: ``contract_*``,
``line_identifier``, ``connection_type_id`` of ``lines`` (ADR-003) — the compliance of T-29,
the appeals of T-47 and the map read them from there.

The preview is the same run without writing: every row gets its verdict — a new line, changed
fields, nothing to change, or an error — and the person applies the same file afterwards. Rows
with an error are skipped, the others are applied together; the caller commits and writes one
audit record with the counts (``describe_action``).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, cast

from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConnectionType, Line, Provider, School
from app.schemas.contracts import (
    ContractImportAction,
    ContractImportReport,
    ContractImportRequest,
    ContractImportRow,
)
from app.services.references import Changes, invalid_field
from app.services.spreadsheet import TableError, excel_date, read_table

# Column → the headers it is recognised by, after ``normalized``.
COLUMNS: dict[str, tuple[str, ...]] = {
    "school_code": ("school_code", "school id", "school_id", "schoolid", "код школы"),
    "provider": ("provider", "provider_name", "поставщик", "провайдер"),
    "line_identifier": (
        "line_identifier",
        "line",
        "идентификатор линии",
        "идентификатор",
        "линия",
        "лицевой счет",
    ),
    "status": ("status", "line_status", "статус", "статус линии", "роль линии", "линия роль"),
    "connection_type": ("connection_type", "тип подключения", "тип", "технология"),
    "contract_number": (
        "contract_number",
        "номер договора",
        "договор",
        "№ договора",
        "no договора",
    ),
    "contract_date": ("contract_date", "дата договора", "дата"),
    "contract_down_mbps": (
        "contract_down_mbps",
        "download",
        "download по договору",
        "договор download",
        "скорость download",
        "скорость приема",
        "скорость входящая",
    ),
    "contract_up_mbps": (
        "contract_up_mbps",
        "upload",
        "upload по договору",
        "договор upload",
        "скорость upload",
        "скорость передачи",
        "скорость исходящая",
    ),
}
REQUIRED = ("school_code", "provider")
COLUMN_TITLES = {"school_code": "School ID", "provider": "Поставщик"}

# Words of the role of a line in the file: the codes of ``LineStatus`` and their captions.
STATUS_WORDS = {
    "main": "main",
    "основная": "main",
    "reserve": "reserve",
    "резервная": "reserve",
    "disabled": "disabled",
    "отключена": "disabled",
}

# Fields of a line the file may fill; a value the file has not is left as it is.
CONTRACT_FIELDS = (
    "line_identifier",
    "connection_type_id",
    "contract_number",
    "contract_date",
    "contract_down_mbps",
    "contract_up_mbps",
)

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y")
NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)")
UNIT_SUFFIX = re.compile(r"[\s,]*\(?\s*мбит\s*/\s*с\s*\)?$")


class RowError(ValueError):
    """A row the import skips; the message is the reason the report shows."""


@dataclass(frozen=True)
class ParsedRow:
    """One row of the file with its cells read; ``None`` — the cell is empty or absent."""

    number: int
    school_code: str
    provider: str
    line_identifier: str | None = None
    status: str | None = None
    connection_type: str | None = None
    contract_number: str | None = None
    contract_date: date | None = None
    contract_down_mbps: float | None = None
    contract_up_mbps: float | None = None


@dataclass
class References:
    """Rows the import matches against, by their keys in lower case."""

    schools: dict[str, School]
    providers: dict[str, Provider]
    connection_types: dict[str, ConnectionType]
    # Lines of every school of the file, the new ones added as they are planned.
    lines: dict[int, list[Line]] = field(default_factory=dict)


def normalized(text: str) -> str:
    """A header or a word as it is compared: lower case, one space, «ё» as «е», no unit."""
    lowered = " ".join(text.lower().replace("ё", "е").split())
    return UNIT_SUFFIX.sub("", lowered).strip(" .:")


def column_map(header: list[str]) -> dict[str, int]:
    """Field → index of its column in the file; the required ones must be there."""
    found: dict[str, int] = {}
    for index, title in enumerate(header):
        name = normalized(title)
        for column, aliases in COLUMNS.items():
            if column not in found and name in aliases:
                found[column] = index
                break
    missing = [COLUMN_TITLES[column] for column in REQUIRED if column not in found]
    if missing:
        raise invalid_field("content", f"В файле нет колонок: {', '.join(missing)}")
    return found


def parse_speed(text: str) -> float:
    """«100», «100,5», «100 Мбит/с» → 100.0; anything else or zero is an error."""
    match = NUMBER.match(text.replace(" ", " "))
    value = float(match.group(1).replace(",", ".")) if match else 0.0
    if value <= 0:
        raise RowError(f"скорость «{text}» — не число больше нуля")
    return value


def parse_date(text: str) -> date:
    """«15.01.2026», «2026-01-15», «15/01/2026» or the serial number of Excel."""
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    try:
        serial = excel_date(float(text.replace(",", ".")))
    except ValueError:
        serial = None
    if serial is None:
        raise RowError(f"дата «{text}» — не дата вида ДД.ММ.ГГГГ")
    return serial


def parse_status(text: str) -> str:
    status = STATUS_WORDS.get(normalized(text))
    if status is None:
        raise RowError(f"статус линии «{text}»: основная, резервная или отключена")
    return status


def parse_row(number: int, cells: list[str], columns: dict[str, int]) -> ParsedRow:
    """Cells of one row read by their columns; an unreadable cell is a ``RowError``."""

    def cell(column: str) -> str | None:
        index = columns.get(column)
        value = cells[index] if index is not None and index < len(cells) else ""
        return value.strip() or None

    school_code, provider = cell("school_code"), cell("provider")
    if school_code is None or provider is None:
        raise RowError("не заполнены School ID или поставщик")
    down, up, signed, status = (
        cell("contract_down_mbps"),
        cell("contract_up_mbps"),
        cell("contract_date"),
        cell("status"),
    )
    return ParsedRow(
        number=number,
        school_code=school_code,
        provider=provider,
        line_identifier=cell("line_identifier"),
        status=None if status is None else parse_status(status),
        connection_type=cell("connection_type"),
        contract_number=cell("contract_number"),
        contract_date=None if signed is None else parse_date(signed),
        contract_down_mbps=None if down is None else parse_speed(down),
        contract_up_mbps=None if up is None else parse_speed(up),
    )


def parse_file(body: ContractImportRequest) -> list[ParsedRow | tuple[int, str]]:
    """Rows of the file, each parsed or paired with the reason it could not be."""
    try:
        table = read_table(body.content, body.file_name)
    except TableError as error:
        raise invalid_field("content", str(error)) from error
    if not table:
        raise invalid_field("content", "Файл пуст: нет строки заголовка")
    columns = column_map(table[0])
    parsed: list[ParsedRow | tuple[int, str]] = []
    for number, cells in enumerate(table[1:], start=2):
        try:
            parsed.append(parse_row(number, cells, columns))
        except RowError as error:
            parsed.append((number, str(error)))
    return parsed


async def load_references(session: AsyncSession, rows: list[ParsedRow]) -> References:
    """Schools, providers, connection types and the lines of the schools the file names."""
    codes = {row.school_code.lower() for row in rows}
    schools = {
        school.school_code.lower(): school
        for school in await session.scalars(select(School))
        if school.school_code.lower() in codes
    }
    providers = {
        provider.name.lower(): provider for provider in await session.scalars(select(Provider))
    }
    connection_types: dict[str, ConnectionType] = {}
    for connection_type in await session.scalars(select(ConnectionType)):
        connection_types[connection_type.code.lower()] = connection_type
        connection_types[normalized(connection_type.name)] = connection_type
    lines: dict[int, list[Line]] = {school.id: [] for school in schools.values()}
    if lines:
        for line in await session.scalars(
            select(Line).where(Line.school_id.in_(lines)).order_by(Line.id)
        ):
            lines[line.school_id].append(line)
    return References(schools, providers, connection_types, lines)


def find_line(lines: list[Line], provider_id: int, identifier: str | None) -> Line | None:
    """The line of the provider the row is about: by the identifier when the file has one,
    else the main line of the provider, else its first other line."""
    of_provider = [line for line in lines if line.provider_id == provider_id]
    if identifier is not None:
        wanted = identifier.lower()
        for line in of_provider:
            if (line.line_identifier or "").lower() == wanted:
                return line
        # The registry names a line the panel has not named yet: the only unnamed one is it.
        unnamed = [line for line in of_provider if line.line_identifier is None]
        return unnamed[0] if len(unnamed) == 1 else None
    for status in ("main", "reserve", "disabled"):
        for line in of_provider:
            if line.status == status:
                return line
    return None


def new_line_status(row: ParsedRow, lines: list[Line]) -> str:
    """Role of the line the row creates: the one of the file, else main when the school has
    none, else reserve; a second main line is an error, as in the panel (T-35)."""
    has_main = any(line.status == "main" for line in lines)
    if row.status is None:
        return "reserve" if has_main else "main"
    if row.status == "main" and has_main:
        raise RowError("у школы уже есть основная линия: укажите «резервная» или идентификатор")
    return row.status


def wanted_values(row: ParsedRow, references: References) -> dict[str, Any]:
    """Values of ``CONTRACT_FIELDS`` the row carries; an empty cell carries nothing."""
    values: dict[str, Any] = {}
    if row.connection_type is not None:
        connection_type = references.connection_types.get(normalized(row.connection_type))
        if connection_type is None:
            raise RowError(f"тип подключения «{row.connection_type}» не найден")
        values["connection_type_id"] = connection_type.id
    for name in ("line_identifier", "contract_number", "contract_date"):
        if getattr(row, name) is not None:
            values[name] = getattr(row, name)
    for name in ("contract_down_mbps", "contract_up_mbps"):
        if getattr(row, name) is not None:
            values[name] = getattr(row, name)
    return values


def jsonable(changes: Changes) -> Changes:
    """Changes with dates as JSON values: the report and ``audit_log.changes`` are JSON."""
    return cast(Changes, to_jsonable_python(changes))


def verdict(
    session: AsyncSession, row: ParsedRow, references: References, *, apply: bool
) -> tuple[ContractImportRow, Line]:
    """What the row does to the lines of its school and the line it is about; with ``apply``
    it does it. A new line has no id until the caller flushes."""
    school = references.schools.get(row.school_code.lower())
    if school is None:
        raise RowError(f"школа с School ID «{row.school_code}» не найдена")
    provider = references.providers.get(row.provider.lower())
    if provider is None:
        raise RowError(f"поставщик «{row.provider}» не найден: заведите его в справочнике")
    lines = references.lines.setdefault(school.id, [])
    values = wanted_values(row, references)
    line = find_line(lines, provider.id, row.line_identifier)
    action: ContractImportAction
    changes: Changes
    if line is None:
        status = new_line_status(row, lines)
        line = Line(school_id=school.id, provider_id=provider.id, status=status, **values)
        lines.append(line)
        action = "create"
        changes = {"status": {"old": None, "new": status}} | {
            name: {"old": None, "new": value} for name, value in values.items()
        }
        if apply:
            session.add(line)
    else:
        changes = {
            name: {"old": getattr(line, name), "new": value}
            for name, value in values.items()
            if getattr(line, name) != value
        }
        action = "update" if changes else "unchanged"
        if apply:
            for name, change in changes.items():
                setattr(line, name, change["new"])
    report = ContractImportRow(
        row=row.number,
        school_code=school.school_code,
        school_id=school.id,
        school_name=school.full_name,
        provider_name=provider.name,
        line_id=line.id,
        action=action,
        changes=jsonable(changes) or None,
        error=None,
    )
    return report, line


async def import_contracts(
    session: AsyncSession, body: ContractImportRequest, *, apply: bool
) -> ContractImportReport:
    """Report of the file; with ``apply`` the lines are changed and created — the caller
    commits. Rows with an error are reported and skipped, the others go through."""
    parsed = parse_file(body)
    rows = [item for item in parsed if isinstance(item, ParsedRow)]
    references = await load_references(session, rows)
    items: list[ContractImportRow] = []
    created: list[tuple[ContractImportRow, Line]] = []
    for item in parsed:
        if not isinstance(item, ParsedRow):
            number, reason = item
            items.append(failed_row(number, None, None, reason))
            continue
        try:
            report, line = verdict(session, item, references, apply=apply)
        except RowError as error:
            items.append(failed_row(item.number, item.school_code, item.provider, str(error)))
            continue
        items.append(report)
        if report.action == "create":
            created.append((report, line))
    if apply:
        # The ids of the new lines exist only after the flush.
        await session.flush()
        for report, line in created:
            report.line_id = line.id
    counts = {action: 0 for action in ("create", "update", "unchanged", "error")}
    for entry in items:
        counts[entry.action] += 1
    return ContractImportReport(
        file_name=body.file_name,
        dry_run=not apply,
        rows_total=len(items),
        created=counts["create"],
        updated=counts["update"],
        unchanged=counts["unchanged"],
        failed=counts["error"],
        items=items,
    )


def failed_row(
    number: int, school_code: str | None, provider: str | None, reason: str
) -> ContractImportRow:
    return ContractImportRow(
        row=number,
        school_code=school_code,
        school_id=None,
        school_name=None,
        provider_name=provider,
        line_id=None,
        action="error",
        changes=None,
        error=reason,
    )
