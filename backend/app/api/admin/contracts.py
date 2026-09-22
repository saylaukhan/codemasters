"""Import of a contract registry into the lines of schools (T-87; ТЗ п. 14, п. 20).

Two calls with the same file: the preview reports what the file would change and writes
nothing, the import applies it. The lines get what the panel edits by hand on the school card
(T-35): the number, the date and the speeds of the contract, the identifier and the technology
of the line; a school without such a line gets a new one. The roles that set up schools import
(``schools:write``); one import is one audit record with its counts.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.auth.audit import describe_action
from app.core.db import get_session
from app.schemas.contracts import COLUMNS_HELP, ContractImportReport, ContractImportRequest
from app.services.contract_import import import_contracts

router = APIRouter(
    prefix="/contracts", tags=["admin"], dependencies=[Depends(require("schools:write"))]
)


@router.post(
    "/import/preview",
    summary="Проверить файл договоров: что изменится, без записи",
    description=(
        f"{COLUMNS_HELP} Строка находит линию по School ID и поставщику — и по идентификатору "
        "линии, если он есть; без такой линии строка создаёт новую: основную, если у школы её "
        "нет, иначе резервную. Нечитаемый файл, файл без обязательных колонок или другого "
        "формата — 422 на content. Ничего не записывается и в журнал не попадает."
    ),
)
async def preview_contract_import(
    body: ContractImportRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> ContractImportReport:
    return await import_contracts(session, body, apply=False)


@router.post(
    "/import",
    summary="Импортировать договоры в линии школ",
    description=(
        "То же, что предпросмотр, но с записью: строки с ошибкой пропускаются, остальные "
        "применяются вместе. Пустая ячейка ничего не меняет; статус существующей линии файл не "
        "меняет. Одна запись в журнале аудита: файл, число строк, созданных и изменённых линий."
    ),
)
async def run_contract_import(
    body: ContractImportRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContractImportReport:
    report = await import_contracts(session, body, apply=True)
    await session.commit()
    describe_action(
        request,
        action="import",
        changes={
            "file_name": {"old": None, "new": report.file_name},
            "rows": {"old": None, "new": report.rows_total},
            "created": {"old": None, "new": report.created},
            "updated": {"old": None, "new": report.updated},
            "failed": {"old": None, "new": report.failed},
        },
    )
    return report
