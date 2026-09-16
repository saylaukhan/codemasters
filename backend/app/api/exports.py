"""Export API (plan.md §10 «Экспорт», ТЗ п. 9): create an export, then download its file.

Contract stubs: every endpoint answers 501 until T-30. The same two endpoints serve the
synchronous MVP (T-30…T-32: the file is built within the POST) and background exports (T-33:
the POST answers ``pending``, the GET answers 202 until the file is ready). Exports cover only
the user's scope (ADR-008).
"""

from fastapi import APIRouter, Response, Security, status

from app.core.deps import user_token
from app.core.errors import not_implemented
from app.schemas.errors import Problem
from app.schemas.exports import ExportCreate, ExportJob

router = APIRouter(prefix="/exports", tags=["exports"], dependencies=[Security(user_token)])

FILE_SCHEMA = {"schema": {"type": "string", "format": "binary"}}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать выгрузку: режим, формат, период, фильтры, колонки",
    description=(
        "Сочетания режима и формата: `raw` — замеры в xlsx, csv или json, фильтры device_ids и "
        "statuses, выбор колонок (T-30); `aggregates` — строка на школу в xlsx, csv или json: "
        "school_code, school_name, measurements_count, avg_download_mbps, min_download_mbps, "
        "avg_upload_mbps, avg_ping_ms, problem_count, problem_pct — по основной линии без Wi‑Fi, "
        "как GET /api/analytics (T-31); `school_report` — PDF по одной школе: KPI, графики, число "
        "и длительность простоев, таблица замеров (T-32). Другие сочетания — 422. Неизвестные "
        "или вне области видимости school_ids и device_ids — 422 (ADR-008). До T-33 файл "
        "формируется в запросе и выгрузка приходит ready или failed; с T-33 PDF и выгрузки "
        "больше порога строк из settings (по умолчанию 10 000) приходят pending и формируются "
        "в фоне."
    ),
)
async def create_export(body: ExportCreate) -> ExportJob:
    raise not_implemented("T-30")


@router.get(
    "/{export_id}",
    response_class=Response,
    summary="Файл выгрузки или её состояние",
    description=(
        "Ответ зависит от status выгрузки: ready — 200 с файлом и Content-Disposition; "
        "pending — 202 с выгрузкой, запрос повторяется позже; failed — 409. Выгрузки другого "
        "пользователя, неизвестные и с истёкшим expires_at — 404. Файл отдаётся только с "
        "Authorization: Bearer: панель скачивает его запросом, а не прямой ссылкой."
    ),
    responses={
        200: {
            "description": "Файл выгрузки",
            "headers": {
                "Content-Disposition": {
                    "description": "attachment с именем файла",
                    "schema": {"type": "string"},
                }
            },
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FILE_SCHEMA,
                "text/csv": FILE_SCHEMA,
                "application/json": FILE_SCHEMA,
                "application/pdf": FILE_SCHEMA,
            },
        },
        202: {"model": ExportJob, "description": "Файл ещё формируется (status pending)"},
        404: {"model": Problem, "description": "Выгрузка не найдена или срок хранения истёк"},
        409: {
            "model": Problem,
            "description": "Файл не сформирован (type export_failed), причина — в detail",
        },
    },
)
async def get_export(export_id: int) -> Response:
    raise not_implemented("T-30")
