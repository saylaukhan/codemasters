"""Request and report of the contract import (T-61; ТЗ п. 14; plan.md §10 «Админка»).

The registry of contracts is a CSV or XLSX table: one row per line of a school with the
number, the date and the speeds of its contract. The file goes in the body as base64 — the
API takes JSON only (ADR-009). The report names every row: a new line, changed fields of a
found line, nothing to change, or an error; a preview is the same report without writing.
"""

from typing import Any, Literal, Self

from pydantic import Base64Bytes, BaseModel, Field, model_validator

# The contract registry of the oblast is a few hundred rows; a file larger than this is not it.
MAX_FILE_SIZE = 2 * 1024 * 1024

# What the import did, or would do, with a row of the file.
type ContractImportAction = Literal["create", "update", "unchanged", "error"]

COLUMNS_HELP = (
    "Колонки файла (заголовок — первая строка; регистр и порядок не важны): School ID, "
    "Поставщик — обязательные; Идентификатор линии, Статус линии (основная/резервная), "
    "Тип подключения, Номер договора, Дата договора (ДД.ММ.ГГГГ), Download по договору, "
    "Upload по договору (Мбит/с) — по наличию. Пустая ячейка ничего не меняет."
)


class ContractImportRequest(BaseModel):
    """File of the registry: its name says the format, the content goes as base64."""

    file_name: str = Field(
        min_length=1,
        max_length=255,
        examples=["contracts.xlsx"],
        description="Имя файла: .csv или .xlsx",
    )
    content: Base64Bytes = Field(
        description=f"Содержимое файла в base64, не больше 2 МиБ. {COLUMNS_HELP}"
    )

    @model_validator(mode="after")
    def check_size(self) -> Self:
        if len(self.content) > MAX_FILE_SIZE:
            raise ValueError("файл больше 2 МиБ")
        if not self.file_name.lower().endswith((".csv", ".xlsx")):
            raise ValueError("поддерживаются файлы CSV и XLSX")
        return self


class ContractImportRow(BaseModel):
    """Verdict of the import on one row of the file."""

    row: int = Field(ge=2, description="Номер строки в файле; заголовок — строка 1")
    school_code: str | None = Field(description="School ID из файла")
    school_id: int | None = Field(description="Школа, если найдена")
    school_name: str | None
    provider_name: str | None = Field(description="Поставщик из файла")
    line_id: int | None = Field(description="Найденная или созданная линия")
    action: ContractImportAction
    changes: dict[str, Any] | None = Field(
        description="Изменённые поля линии {поле: {old, new}}; у новой линии old пустой"
    )
    error: str | None = Field(description="Почему строка не применена")


class ContractImportReport(BaseModel):
    """What the file did, or would do, to the lines of the schools."""

    file_name: str
    dry_run: bool = Field(description="true — предпросмотр: ничего не записано")
    rows_total: int = Field(ge=0, description="Строк данных в файле без заголовка")
    created: int = Field(ge=0, description="Новых линий")
    updated: int = Field(ge=0, description="Линий с изменёнными полями договора")
    unchanged: int = Field(ge=0)
    failed: int = Field(ge=0, description="Строк с ошибкой; они пропущены, остальные применены")
    items: list[ContractImportRow]
