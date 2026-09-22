"""T-65: «Забыли пароль?» — одна ссылка, одинаковый ответ, запись в аудит (§4.6 дизайна)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import AuditLog, PasswordResetToken
from tests.factories import PASSWORD, create_settings, create_user
from tests.test_auth import ME, login, problem

REQUEST = "/api/auth/password-reset"
CONFIRM = "/api/auth/password-reset/confirm"
LOGIN_INFO = "/api/auth/login-info"

SMTP_HOST = "smtp.example.kz"
SUPPORT_CONTACT = "admin@edu.vko.kz, +7 7232 00-00-00"
NEW_PASSWORD = "NewPassword2"


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """No SMTP on the server of the tests and no way out to the network from here.

    A test that wants a letter turns the channel on with ``letters``.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("тест не ходит в сеть: отправка письма должна быть подменена")

    monkeypatch.setattr("app.services.password_reset.send_email", no_network)
    return settings


def letters(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> list[tuple[Any, ...]]:
    """Turn the e-mail channel on and remember every letter instead of sending it."""
    sent: list[tuple[Any, ...]] = []
    monkeypatch.setattr(settings, "smtp_host", SMTP_HOST)
    monkeypatch.setattr("app.services.password_reset.send_email", lambda *args: sent.append(args))
    return sent


def token_of(letter: tuple[Any, ...]) -> str:
    """Token of the link in the text of the letter: ``…/password-reset?token=<id>.<secret>``."""
    address, subject, text = letter[1], letter[2], letter[3]
    assert "@" in address and subject
    return text.split("?token=")[1].split()[0]


async def tokens_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(PasswordResetToken)) or 0


async def reset_records(session: AsyncSession) -> list[tuple[str, int | None, Any]]:
    """The ``password_reset`` records of the log: what happened, to whom and with what state."""
    rows = await session.execute(
        select(AuditLog.action, AuditLog.user_id, AuditLog.changes)
        .where(AuditLog.action == "password_reset")
        .order_by(AuditLog.id)
    )
    return [tuple(row) for row in rows.tuples()]


async def test_the_answer_is_the_same_for_a_known_and_an_unknown_email(
    session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    offline: Settings,
) -> None:
    """«Сделано, когда»: ответ одинаков, ссылка уходит только существующему пользователю."""
    await create_settings(session)
    user = await create_user(session, "oblast")
    sent = letters(monkeypatch, offline)

    known = await api_client.post(REQUEST, json={"email": " Oblast@Example.KZ "})
    unknown = await api_client.post(REQUEST, json={"email": "nobody@example.kz"})

    assert (known.status_code, known.text) == (204, "")
    assert (unknown.status_code, unknown.text) == (204, "")
    assert len(sent) == 1
    assert sent[0][1] == user.email
    assert await tokens_count(session) == 1
    assert await reset_records(session) == [
        ("password_reset", user.id, {"reset_link": {"new": "выдана"}})
    ]


async def test_the_link_works_once_and_the_password_really_changes(
    session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    offline: Settings,
) -> None:
    """Одна ссылка — один пароль: повторный переход отказан, старый пароль больше не подходит."""
    await create_settings(session)
    user = await create_user(session, "oblast")
    sent = letters(monkeypatch, offline)
    signed_in = await login(api_client, user.email)
    access = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    asked = await api_client.post(REQUEST, json={"email": user.email})
    assert asked.status_code == 204, asked.text
    token = token_of(sent[0])

    # Правила пароля — те же, что у администрирования пользователей: короткий это 422.
    problem(
        await api_client.post(CONFIRM, json={"token": token, "password": "short"}),
        422,
        "validation_error",
    )
    changed = await api_client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD})
    assert (changed.status_code, changed.text) == (204, "")

    problem(
        await api_client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD}),
        400,
        "invalid_reset_token",
    )
    problem(await login(api_client, user.email, PASSWORD), 401, "invalid_credentials")
    assert (await login(api_client, user.email, NEW_PASSWORD)).status_code == 200
    # Смена пароля поднимает token_version: открытая сессия заканчивается, как при сбросе
    # администратором (app/services/users.py).
    problem(await api_client.get(ME, headers=access), 401, "unauthorized")
    assert await reset_records(session) == [
        ("password_reset", user.id, {"reset_link": {"new": "выдана"}}),
        ("password_reset", user.id, {"reset_link": {"new": "использована"}}),
    ]


async def test_an_expired_or_malformed_link_is_refused_the_same_way(
    session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    offline: Settings,
) -> None:
    """Истёкшая, погашенная и просто не та ссылка отвечают одним type (ADR-009)."""
    await create_settings(session)
    await create_user(session, "admin")
    sent = letters(monkeypatch, offline)
    await api_client.post(REQUEST, json={"email": "admin@example.kz"})
    token = token_of(sent[0])
    row = await session.scalar(select(PasswordResetToken))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    problem(
        await api_client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD}),
        400,
        "invalid_reset_token",
    )
    problem(
        await api_client.post(CONFIRM, json={"token": "1.notatoken", "password": NEW_PASSWORD}),
        400,
        "invalid_reset_token",
    )
    # Старый пароль остался: истёкшая ссылка ничего не меняет.
    assert (await login(api_client, "admin@example.kz")).status_code == 200


async def test_without_smtp_nothing_is_sent_and_the_screen_shows_the_contact(
    session: AsyncSession, api_client: AsyncClient
) -> None:
    """«Сделано, когда»: без SMTP ответ тот же, ссылка не показывается, вместо неё контакт."""
    settings_row = await create_settings(session)
    settings_row.support_contact = SUPPORT_CONTACT
    await session.flush()
    user = await create_user(session, "district")

    answer = await api_client.post(REQUEST, json={"email": user.email})

    assert (answer.status_code, answer.text) == (204, "")
    assert await tokens_count(session) == 0
    assert await reset_records(session) == []
    info = await api_client.get(LOGIN_INFO)
    assert info.status_code == 200, info.text
    assert info.json() == {"password_reset_available": False, "support_contact": SUPPORT_CONTACT}


async def test_a_blocked_user_gets_no_link_and_the_answer_does_not_say_so(
    session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    offline: Settings,
) -> None:
    """Блокировка не раскрывается ответом и не даёт ссылку (ТЗ п. 16)."""
    await create_settings(session)
    await create_user(session, "provider", is_active=False)
    sent = letters(monkeypatch, offline)

    answer = await api_client.post(REQUEST, json={"email": "provider@example.kz"})

    assert (answer.status_code, answer.text) == (204, "")
    assert sent == []
    assert await tokens_count(session) == 0
    info = await api_client.get(LOGIN_INFO)
    assert info.json() == {"password_reset_available": True, "support_contact": ""}
