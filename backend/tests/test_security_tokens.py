"""Cost and format of the device token check, and what stays on argon2 (ADR-005, T-56).

No database: the hashes are pure functions, and ``current_device`` is called with a session
stubbed out below. That is deliberate — the rest of the agent tests need the container of
``conftest.py``, while the behaviour this module guards (which algorithm hashes what, that an
old hash is still accepted, that 401 and 403 are unchanged) is exactly what must keep working
on a machine where the container cannot start.

What is checked here:

* a token hash says which algorithm made it, and holds neither the token nor argon2;
* the right token verifies, a wrong one does not, a damaged hash is a mismatch and not a crash;
* an argon2 hash written before the split is still accepted, and the first request that uses
  it replaces it with the sha256 one — blocked device included;
* that replacement names the hash it replaces, so a token rotated by another request in the
  same moment is not overwritten by the token it revoked (ADR-005, ТЗ п. 16);
* a replacement the database refuses is a cost and not a refusal: the request still passes;
* passwords and installation codes are still argon2, which is the point of splitting them off;
* argon2 that remains does not sit in the event loop.
"""

import asyncio
import hmac
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import Update, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.deps import DEVICE_SCHEME, UNAUTHORIZED_DETAIL, current_device
from app.core.errors import ApiError
from app.core.security import (
    TOKEN_HASH_PREFIX,
    burn_password_check_async,
    format_device_token,
    hash_password,
    hash_password_async,
    hash_secret,
    hash_token,
    new_device_secret,
    new_enrollment_secret,
    password_needs_rehash,
    token_needs_rehash,
    verify_password,
    verify_password_async,
    verify_secret,
    verify_secret_async,
    verify_token,
    verify_token_async,
)
from app.models import Device

ARGON2_PREFIX = "$argon2id$"

DEVICE_ID = 17


@dataclass(frozen=True)
class FakeResult:
    """What ``session.execute`` gives back: the ``RETURNING`` of the rows the UPDATE matched."""

    returned: int | None

    def scalar_one_or_none(self) -> int | None:
        return self.returned


class FakeSession:
    """The calls ``current_device`` makes on a session, answered the way a row would answer.

    ``get`` returns the one device it was built with, so an unknown id is ``None`` the way the
    database answers it. ``stored`` is kept apart from the object on purpose: the object holds
    what this request read, ``stored`` holds what the row holds now, and the two differ exactly
    when another session has written in between. ``execute`` applies the UPDATE of the rehash
    only when its condition still finds ``stored``, which is what makes that race visible in a
    test at all; ``commits`` counts the rehash, which must happen once and never for a request
    that was refused.
    """

    def __init__(self, device: Device | None = None, *, failing: bool = False) -> None:
        self.device = device
        self.stored = device.token_hash if device is not None else None
        # Written by the UPDATE and visible to nobody until the commit, as in a transaction.
        self.pending: str | None = None
        self.failing = failing
        self.commits = 0
        self.rollbacks = 0
        self.refreshes = 0
        self.statements: list[Update] = []

    async def get(self, model: type[Any], key: int) -> Device | None:
        if self.device is None or self.device.id != key:
            return None
        return self.device

    async def execute(self, statement: Update) -> FakeResult:
        self.statements.append(statement)
        params = statement.compile().params
        if self.device is None or params["id_1"] != self.device.id:
            return FakeResult(None)
        # The condition of the UPDATE, evaluated where the database would evaluate it. An
        # UPDATE without one — ``WHERE id = :id`` alone — matches the row whatever it holds,
        # which is the behaviour the test of a rotation has to be able to see and fail on.
        if "token_hash_1" in params and params["token_hash_1"] != self.stored:
            return FakeResult(None)
        self.pending = params["token_hash"]
        return FakeResult(self.device.id)

    async def commit(self) -> None:
        if self.failing:
            raise OperationalError("UPDATE devices SET token_hash=%s", {}, Exception("нет связи"))
        if self.pending is not None:
            self.stored, self.pending = self.pending, None
        self.commits += 1

    async def rollback(self) -> None:
        self.pending = None
        self.rollbacks += 1

    async def refresh(self, instance: Device) -> None:
        """A rollback expires the object; the caller reads it again before using it."""
        self.refreshes += 1
        instance.token_hash = cast(str, self.stored)


def make_device(token_hash: str, *, status: str = "active") -> Device:
    device = Device(device_uid="PC-1", monitoring_point_id=1, token_hash=token_hash)
    device.id = DEVICE_ID
    device.status = status
    return device


def fake_request() -> Any:
    """Enough of ``Request`` for the dependency: it only writes ``state.device_id``."""
    return SimpleNamespace(state=SimpleNamespace())


async def authenticate(session: FakeSession, header: str | None, request: Any) -> Device:
    return await current_device(request, header, cast(AsyncSession, session))


# --- format of a token hash -------------------------------------------------------------


def test_token_hash_names_its_algorithm_and_hides_the_token() -> None:
    secret = new_device_secret()

    hashed = hash_token(secret)

    assert hashed.startswith(TOKEN_HASH_PREFIX)
    assert not hashed.startswith(ARGON2_PREFIX)
    # sha256 in hex after the prefix, and the token itself nowhere in it.
    assert len(hashed) == len(TOKEN_HASH_PREFIX) + 64
    assert secret not in hashed


def test_token_hash_is_the_same_every_time() -> None:
    """Without a salt the hash can be compared instead of recomputed row by row: that is what
    makes the check a comparison and not a key derivation."""
    secret = new_device_secret()

    assert hash_token(secret) == hash_token(secret)
    assert hash_token(secret) != hash_token(new_device_secret())


def test_new_token_hash_does_not_need_a_rehash() -> None:
    assert not token_needs_rehash(hash_token(new_device_secret()))


def test_argon2_token_hash_is_marked_for_a_rehash() -> None:
    assert token_needs_rehash(hash_secret(new_device_secret()))


# --- checking a token -------------------------------------------------------------------


def test_verify_token_accepts_the_token_and_refuses_everything_else() -> None:
    secret = new_device_secret()
    hashed = hash_token(secret)

    assert verify_token(secret, hashed)
    assert not verify_token(new_device_secret(), hashed)
    assert not verify_token(secret + "x", hashed)
    assert not verify_token("", hashed)


def test_verify_token_accepts_a_hash_written_by_argon2() -> None:
    """Devices registered before the split keep an argon2 hash: the token was handed out once
    and never stored, so nothing but the device itself can produce it again."""
    secret = new_device_secret()
    legacy = hash_secret(secret)

    assert verify_token(secret, legacy)
    assert not verify_token(new_device_secret(), legacy)


@pytest.mark.parametrize(
    "damaged",
    [
        "",
        "sha256$",
        TOKEN_HASH_PREFIX + "zz",
        "$argon2id$broken",
        "мусор",
        # Both branches get a value with a character outside ASCII in it. Neither library
        # takes one: argon2 encodes the stored hash as ASCII before parsing it, and
        # ``hmac.compare_digest`` raises ``TypeError`` on two such strings instead of
        # answering False. A row the API cannot read is 401, not 500.
        TOKEN_HASH_PREFIX + "мусор",
        TOKEN_HASH_PREFIX + "э" * 64,
        TOKEN_HASH_PREFIX + "a" * 63 + "я",
        "$argon2id$" + "я" * 20,
    ],
)
def test_verify_token_treats_a_damaged_hash_as_a_mismatch(damaged: str) -> None:
    secret = new_device_secret()

    assert not verify_token(secret, damaged)


async def test_verify_token_async_treats_a_damaged_hash_as_a_mismatch() -> None:
    """The async path reads the same column and must refuse the same values."""
    secret = new_device_secret()

    for damaged in [TOKEN_HASH_PREFIX + "мусор", TOKEN_HASH_PREFIX + "э" * 64, "мусор", ""]:
        assert not await verify_token_async(secret, damaged), damaged


async def test_a_damaged_hash_in_the_row_is_401_and_not_500() -> None:
    """What the two tests above protect: the value comes out of ``devices.token_hash``, so a
    row that cannot be read must end as the refusal every unknown token gets (ADR-005)."""
    session = FakeSession(make_device(TOKEN_HASH_PREFIX + "мусор"))
    token = format_device_token(DEVICE_ID, new_device_secret())

    with pytest.raises(ApiError) as raised:
        await authenticate(session, f"{DEVICE_SCHEME} {token}", fake_request())

    assert raised.value.status == 401
    assert session.commits == 0


def test_verify_token_compares_in_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The comparison goes through ``hmac.compare_digest`` on two values of equal length, so
    its duration tells a caller neither how many characters matched nor that any did."""
    calls: list[tuple[str, str]] = []
    real = hmac.compare_digest

    def recording(left: Any, right: Any) -> bool:
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(security.hmac, "compare_digest", recording)
    secret = new_device_secret()

    assert verify_token(secret, hash_token(secret))
    assert not verify_token(new_device_secret(), hash_token(secret))

    assert len(calls) == 2
    assert all(len(left) == len(right) for left, right in calls)


async def test_verify_token_async_answers_the_same_in_both_formats() -> None:
    secret = new_device_secret()
    other = new_device_secret()

    for hashed in (hash_token(secret), hash_secret(secret)):
        assert await verify_token_async(secret, hashed)
        assert not await verify_token_async(other, hashed)


# --- what stays on argon2 ---------------------------------------------------------------


def test_password_is_still_hashed_by_argon2() -> None:
    """A password is chosen by a human: the holding cost is the protection (ТЗ п. 12)."""
    hashed = hash_password("Password1")

    assert hashed.startswith(ARGON2_PREFIX)
    assert verify_password("Password1", hashed)
    assert not verify_password("Password2", hashed)
    assert not password_needs_rehash(hashed)


def test_installation_code_is_still_hashed_by_argon2() -> None:
    """Fifty bits typed by hand (ADR-005): short enough to be worth slowing down."""
    secret = new_enrollment_secret()
    hashed = hash_secret(secret)

    assert hashed.startswith(ARGON2_PREFIX)
    assert verify_secret(secret, hashed)
    assert not verify_secret(new_enrollment_secret(), hashed)


def test_device_secret_is_long_enough_not_to_need_argon2() -> None:
    """32 bytes of ``secrets`` in url-safe base64: 43 characters, 256 bits, all different."""
    drawn = [new_device_secret() for _ in range(64)]

    assert all(len(secret) >= 43 for secret in drawn)
    assert len(set(drawn)) == len(drawn)


async def test_argon2_wrappers_keep_the_answers_of_the_plain_functions() -> None:
    password = "Password1"
    hashed = await hash_password_async(password)

    assert hashed.startswith(ARGON2_PREFIX)
    assert await verify_password_async(password, hashed)
    assert not await verify_password_async("Password2", hashed)
    # Spends the same argon2 for an unknown e-mail and answers nothing.
    assert await burn_password_check_async(password) is None

    secret = new_enrollment_secret()
    code_hash = await security.hash_secret_async(secret)
    assert code_hash.startswith(ARGON2_PREFIX)
    assert await verify_secret_async(secret, code_hash)


async def test_argon2_leaves_the_event_loop_free() -> None:
    """The point of the wrappers: while argon2 runs, the loop keeps serving other requests."""
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.001)

    ticker = asyncio.create_task(tick())
    await asyncio.sleep(0)
    try:
        await verify_secret_async("Password1", hash_password("Password1"))
    finally:
        ticker.cancel()

    assert ticks > 1


# --- the dependency ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Device",
        f"{DEVICE_SCHEME} ",
        "Bearer 17.abcdefghijklmnop",
        f"{DEVICE_SCHEME} 17",
        f"{DEVICE_SCHEME} 17.короткий",
        f"{DEVICE_SCHEME} device.abcdefghijklmnop",
    ],
)
async def test_a_header_that_is_not_a_token_is_401(header: str | None) -> None:
    session = FakeSession(make_device(hash_token(new_device_secret())))
    request = fake_request()

    with pytest.raises(ApiError) as raised:
        await authenticate(session, header, request)

    assert raised.value.status == 401
    assert raised.value.detail == UNAUTHORIZED_DETAIL
    assert raised.value.headers == {"WWW-Authenticate": DEVICE_SCHEME}
    # Nothing was proved, so nothing is written against a device id (app/auth/audit.py).
    assert not hasattr(request.state, "device_id")
    assert session.commits == 0


async def test_an_unknown_device_is_401() -> None:
    session = FakeSession(None)
    request = fake_request()
    token = format_device_token(DEVICE_ID, new_device_secret())

    with pytest.raises(ApiError) as raised:
        await authenticate(session, f"{DEVICE_SCHEME} {token}", request)

    assert raised.value.status == 401
    assert not hasattr(request.state, "device_id")


@pytest.mark.parametrize("hasher", [hash_token, hash_secret])
async def test_a_wrong_secret_is_401_in_either_format(hasher: Any) -> None:
    session = FakeSession(make_device(hasher(new_device_secret())))
    request = fake_request()
    token = format_device_token(DEVICE_ID, new_device_secret())

    with pytest.raises(ApiError) as raised:
        await authenticate(session, f"{DEVICE_SCHEME} {token}", request)

    assert raised.value.status == 401
    # A token that was not proved must not upgrade the hash of the row it aimed at.
    assert session.commits == 0


async def test_a_valid_token_returns_the_device_without_writing_anything() -> None:
    secret = new_device_secret()
    device = make_device(hash_token(secret))
    session = FakeSession(device)
    request = fake_request()

    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    returned = await authenticate(session, header, request)

    assert returned is device
    assert request.state.device_id == DEVICE_ID
    assert session.commits == 0


async def test_an_old_argon2_hash_is_accepted_and_replaced() -> None:
    """The upgrade the migration could not do: the token comes back only in the request."""
    secret = new_device_secret()
    device = make_device(hash_secret(secret))
    session = FakeSession(device)
    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    returned = await authenticate(session, header, fake_request())

    assert returned is device
    assert device.token_hash == hash_token(secret)
    assert session.stored == hash_token(secret)
    assert session.commits == 1

    # The next request of the same agent costs sha256 and writes nothing more.
    again = FakeSession(device)
    assert await authenticate(again, header, fake_request()) is device
    assert again.commits == 0
    assert again.statements == []


async def test_the_upgrade_names_the_hash_it_replaces() -> None:
    """The UPDATE is conditional, and this is the condition: ``WHERE token_hash = <the value
    this request read>``. Without it the statement would be ``WHERE id = :id`` and would
    overwrite whatever another session wrote in the meantime."""
    secret = new_device_secret()
    legacy = hash_secret(secret)
    session = FakeSession(make_device(legacy))
    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    await authenticate(session, header, fake_request())

    params = session.statements[0].compile().params
    assert params["id_1"] == DEVICE_ID
    assert params["token_hash_1"] == legacy
    assert params["token_hash"] == hash_token(secret)


async def test_a_rotation_during_the_request_survives_the_upgrade() -> None:
    """T-36 and ТЗ п. 16: a rotation answers a leaked token, so it must not be undone by the
    request of the very agent that is still using the old one.

    An agent has several requests in the air at once — the heartbeat, the queue, the
    configuration — and one of them is ``POST /api/agent/token``. Here the rotation lands
    between the read of the row and the rehash: the object still holds the argon2 hash this
    request verified, the row already holds the sha256 hash of the new token. An unconditional
    UPDATE would put the old token back in force and lock the agent out of the new one.
    """
    old = new_device_secret()
    device = make_device(hash_secret(old))
    session = FakeSession(device)
    rotated = hash_token(new_device_secret())
    # What ``rotate_token`` commits from another session while this request is verifying.
    session.stored = rotated

    returned = await authenticate(
        session, f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, old)}", fake_request()
    )

    # The request itself was authenticated by the row it read, so it is not refused.
    assert returned is device
    # But the rotation stands: the new token keeps working and the old one is gone.
    assert session.stored == rotated
    assert session.commits == 1


async def test_the_upgraded_object_holds_no_pending_change() -> None:
    """The conditional UPDATE is worth nothing if the endpoint then writes the column again.

    Assigning ``device.token_hash`` would leave a pending change on the object, and the commit
    of the endpoint would flush it as ``SET token_hash = … WHERE id = :id`` — the very
    unconditional write the rehash avoids, only later in the same request. The value is
    therefore put on the object as an already-committed one.
    """
    secret = new_device_secret()
    device = make_device(hash_secret(secret))
    session = FakeSession(device)
    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    await authenticate(session, header, fake_request())

    assert device.token_hash == hash_token(secret)
    assert not inspect(device).attrs.token_hash.history.has_changes()


async def test_an_upgrade_that_cannot_be_written_does_not_refuse_the_request() -> None:
    """Before this path wrote anything, authenticating an agent never touched the database.

    A lock, a timeout or a dropped connection must therefore not turn a valid request into a
    500: the token has been proved, and an upgrade that failed only costs the next request
    another argon2.
    """
    secret = new_device_secret()
    device = make_device(hash_secret(secret))
    session = FakeSession(device, failing=True)
    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    returned = await authenticate(session, header, fake_request())

    assert returned is device
    assert session.rollbacks == 1
    # The rollback expires the object, so it is read again before the status is looked at.
    assert session.refreshes == 1
    # Nothing was written, so the row is still the one the next request will try to upgrade.
    assert device.token_hash == session.stored
    assert token_needs_rehash(cast(str, session.stored))


async def test_a_blocked_device_is_403_and_keeps_its_row() -> None:
    secret = new_device_secret()
    device = make_device(hash_token(secret), status="blocked")
    session = FakeSession(device)
    request = fake_request()

    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    with pytest.raises(ApiError) as raised:
        await authenticate(session, header, request)

    assert raised.value.status == 403
    assert raised.value.type == "device_blocked"
    # The refusal is logged against the device it came from (ТЗ п. 16, п. 20).
    assert request.state.device_id == DEVICE_ID


async def test_a_blocked_device_stops_costing_argon2() -> None:
    """An agent whose device is blocked keeps calling: its old hash is upgraded all the same,
    so the refusal costs sha256 from the second request on."""
    secret = new_device_secret()
    device = make_device(hash_secret(secret), status="blocked")
    session = FakeSession(device)
    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, secret)}"

    with pytest.raises(ApiError):
        await authenticate(session, header, fake_request())

    assert device.token_hash == hash_token(secret)
    assert session.commits == 1


async def test_a_rotated_token_replaces_the_old_one() -> None:
    """T-36: the panel asks for a rotation, the agent calls ``POST /api/agent/token``, and the
    token it was using stops working the moment the new hash is stored."""
    old = new_device_secret()
    device = make_device(hash_token(old))
    new = new_device_secret()
    device.token_hash = hash_token(new)
    session = FakeSession(device)

    stale = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, old)}"
    with pytest.raises(ApiError) as raised:
        await authenticate(session, stale, fake_request())
    assert raised.value.status == 401

    header = f"{DEVICE_SCHEME} {format_device_token(DEVICE_ID, new)}"
    assert await authenticate(FakeSession(device), header, fake_request()) is device
