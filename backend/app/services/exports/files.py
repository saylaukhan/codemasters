"""Files of a raw export: XLSX, CSV and JSON of the same records (ТЗ п. 9, T-30).

XLSX and CSV are for a person: Russian headers, statuses in words, date ``ДД.ММ.ГГГГ``. CSV is
what Excel with the Russian locale opens by double-click: UTF-8 with a BOM, ``;`` between the
fields, a decimal comma. JSON is for a program: the column codes as keys, codes as values,
ISO date and time, dot decimals.
"""

import csv
import json
from collections.abc import Sequence
from datetime import date
from io import StringIO
from typing import Any

from app.schemas.exports import ExportColumn, ExportFormat
from app.services.exports.columns import COLUMN_TITLES, VALUE_LABELS
from app.services.exports.xlsx import Cell, xlsx_bytes

MEDIA_TYPES: dict[ExportFormat, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "pdf": "application/pdf",
}

SHEET_NAME = "Замеры"


def human_value(column: ExportColumn, value: Any) -> Cell:
    """Value of a record as a person reads it in XLSX and CSV."""
    if value is None:
        return None
    if column in VALUE_LABELS:
        return VALUE_LABELS[column].get(value, value)
    if column == "date":
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    return value


def csv_value(value: Cell) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value).replace(".", ",")
    return str(value)


def export_file(
    file_format: ExportFormat, columns: Sequence[ExportColumn], records: Sequence[dict[str, Any]]
) -> bytes:
    """File of ``records`` with ``columns`` in their order."""
    if file_format == "json":
        chosen = [{column: record[column] for column in columns} for record in records]
        return json.dumps(chosen, ensure_ascii=False).encode()
    header = [COLUMN_TITLES[column] for column in columns]
    rows = ([human_value(column, record[column]) for column in columns] for record in records)
    if file_format == "xlsx":
        return xlsx_bytes(SHEET_NAME, header, rows)
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    writer.writerows([csv_value(value) for value in row] for row in rows)
    return ("﻿" + buffer.getvalue()).encode()
