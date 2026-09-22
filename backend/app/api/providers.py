"""Providers of the panel (plan.md §10, ТЗ п. 14, п. 19): the score, the card and the act.

The screen of the claim work (docs/design/README.md §6.3): a row per provider with its score
for the period, the card of one provider with its schools and the lines whose contract is below
the norm, and the act of non-compliance as a PDF. The numbers are the analytics of T-27 and
T-45 grouped by provider, so the rows stay inside the user's scope (ADR-008): a district sees
only the providers of its own schools and a provider only itself. Reading the analytics is
reading a provider's score, so both endpoints ask for ``analytics:read``.
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require
from app.core.db import get_session
from app.schemas.analytics import AnalyticsPeriod
from app.schemas.errors import Problem
from app.schemas.providers import ProviderScoreDetail, ProviderScoreReport
from app.services.provider_act import provider_act, provider_act_pdf
from app.services.provider_score import provider_score_detail, provider_score_report

router = APIRouter(
    prefix="/providers", tags=["providers"], dependencies=[Depends(require("analytics:read"))]
)

PROVIDER_NOT_FOUND: dict[str, Any] = {"model": Problem, "description": "Поставщик не найден"}

PERIOD = Annotated[
    AnalyticsPeriod,
    Query(description="today, 7 или 30 суток с текущими, custom — period_from и period_to"),
]
PERIOD_FROM = Annotated[
    AwareDatetime | None,
    Query(description="Начало, включительно; только и обязательно при period=custom"),
]
PERIOD_TO = Annotated[
    AwareDatetime | None,
    Query(description="Конец, не включительно; только и обязательно при period=custom"),
]


@router.get(
    "/score",
    summary="Оценка поставщиков за период",
    description=(
        "Строка на каждого поставщика, доступного пользователю (ADR-008), по имени. Замеры, "
        "доступность и доля ниже договора — из агрегатов через аналитику T-27; инциденты — "
        "T-45; реакция — время до первой смены статуса инцидента. Оценка — 100 минус штрафы "
        "частей; веса, порог «ниже нормы» и норма реакции — настройки (ТЗ п. 11, п. 20). Окна "
        "плановых работ пока не исключаются: календарь появится в T-70."
    ),
)
async def get_provider_score(
    period: PERIOD,
    period_from: PERIOD_FROM = None,
    period_to: PERIOD_TO = None,
    region_id: Annotated[int | None, Query(description="Район или город (regions)")] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderScoreReport:
    return await provider_score_report(
        session,
        period=period,
        period_from=period_from,
        period_to=period_to,
        region_id=region_id,
        now=datetime.now(UTC),
    )


@router.get(
    "/{provider_id}/score",
    summary="Карточка поставщика: оценка, школы, договор ниже норматива",
    description=(
        "Те же числа по одному поставщику плюс его школы со статусом и линии, у которых "
        "договорная скорость ниже порога применимого профиля («не претензия»: нужен новый "
        "договор, а не обращение). Поставщик, ни одной линии которого пользователь не видит, — "
        "404."
    ),
    responses={404: PROVIDER_NOT_FOUND},
)
async def get_provider_card(
    provider_id: int,
    period: PERIOD,
    period_from: PERIOD_FROM = None,
    period_to: PERIOD_TO = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderScoreDetail:
    return await provider_score_detail(
        session,
        provider_id,
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=datetime.now(UTC),
    )


@router.get(
    "/{provider_id}/act",
    summary="Акт о несоответствии: PDF по поставщику за период",
    response_class=Response,
    description=(
        "Замеры ниже договорной скорости с порогами и договорными значениями из "
        "thresholds_snapshot каждого замера, а не из профиля и договора на сегодня (ТЗ п. 11). "
        "Генератор — тот же, что у обращения (T-48)."
    ),
    responses={
        200: {
            "description": "PDF-файл акта",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: PROVIDER_NOT_FOUND,
    },
)
async def get_provider_act(
    provider_id: int,
    period: PERIOD,
    period_from: PERIOD_FROM = None,
    period_to: PERIOD_TO = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    act = await provider_act(
        session,
        provider_id,
        period=period,
        period_from=period_from,
        period_to=period_to,
        now=datetime.now(UTC),
    )
    # The name is Cyrillic, an HTTP header is latin-1: the name goes as RFC 5987 (ADR-009).
    name = f"Акт — {act.provider_name}.pdf"
    return Response(
        provider_act_pdf(act),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="provider-act.pdf"; '
            f"filename*=UTF-8''{quote(name)}"
        },
    )
