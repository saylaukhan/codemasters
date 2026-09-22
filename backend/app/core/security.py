"""Secrets the API checks: device tokens, installation codes, passwords and panel JWTs.

No secret is stored: the database keeps only a hash of it — ``devices.token_hash``,
``enrollment_codes.code_hash``, ``users.password_hash`` (ТЗ п. 12). Every secret starts with
the id of its own row (``17.<random>`` for a token, ``VKO-0011-...`` for a code) because a
hash with a random salt cannot be looked up: the id selects exactly one row and the hash
checks the random part, so a wrong id is as useless as a wrong secret.

Which hash, and why two of them:

* **argon2id** — for a secret a person can be made to guess. A panel password is chosen by a
  human, and an installation code is 50 bits typed by hand (``new_enrollment_secret``): both
  are worth slowing an attacker down, so they cost 19 MiB and two passes — the minimum OWASP
  recommends — on every check.
* **sha256** — for a device token. ``new_device_secret`` is 32 random bytes from ``secrets``:
  256 bits, nothing to guess and nothing an attacker can shorten by trying, so the holding
  cost of argon2 buys no security here and only spends the server's CPU. The right tool is a
  fast cryptographic digest compared in constant time (``hmac.compare_digest``). It mattered:
  one check cost tens of milliseconds of the event loop on every request of every agent, and
  a thousand agents send their queues at once (T-56, ТЗ п. 3).

The stored value names its algorithm: a token hash starts with ``sha256$``, and anything else
in ``devices.token_hash`` is an argon2 hash written before this split. Tokens handed out
earlier cannot be rehashed by a migration — the server never kept them — so the old format is
still accepted and replaced the first time the agent shows the token it already has
(``token_needs_rehash``, ``app/core/deps.py``).

argon2 that remains — the panel login, the registration of a device, a password reset — never
runs in the event loop: the ``_async`` wrappers below move it to a small pool of threads, and
async code calls those instead of the plain functions.

Panel JWTs (ADR-009) are HS256 signed with ``SECRET_KEY``: access for 15 minutes, refresh in
the httpOnly cookie. Only the header this module writes is accepted, so a token cannot choose
its own algorithm; ``typ`` keeps a refresh token out of ``Authorization`` and back.
"""

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)

# One argon2 check holds 19 MiB and a core for tens of milliseconds. The default executor of
# asyncio would grow to 32 threads — 600 MiB of a login flood — so argon2 gets a pool of its
# own, small enough to bound the memory and wide enough to use the cores of the container.
# Requests over that width wait in its queue, which is the event loop's business, not the
# loop's thread: nothing here blocks the loop.
ARGON2_THREADS = 4
_ARGON2_POOL = ThreadPoolExecutor(max_workers=ARGON2_THREADS, thread_name_prefix="argon2")


async def _off_loop[T](work: Callable[[], T]) -> T:
    """Run one argon2 call in ``_ARGON2_POOL`` and give the event loop back meanwhile."""
    return await asyncio.get_running_loop().run_in_executor(_ARGON2_POOL, work)


# Crockford base32: no I, L, O, U, so a code read over the phone has one spelling only.
CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# What a human may type instead: the letters Crockford maps back to digits.
CODE_ALIASES = str.maketrans({"O": "0", "I": "1", "L": "1"})

ENROLLMENT_CODE_PREFIX = "VKO"
# Id of the row, then the random part in two groups: VKO-0011-7F3K9-2QD4X.
ENROLLMENT_ID_LENGTH = 4
ENROLLMENT_SECRET_LENGTH = 10
# Matches the part after the prefix: the prefix itself holds an "O" the aliases would fold.
ENROLLMENT_CODE_RE = re.compile(
    rf"^([{CODE_ALPHABET}]{{{ENROLLMENT_ID_LENGTH}}})"
    rf"-([{CODE_ALPHABET}]{{5}})-([{CODE_ALPHABET}]{{5}})$"
)

# Device token: id of the device, a dot, and 32 random bytes in url-safe base64.
DEVICE_SECRET_BYTES = 32
DEVICE_TOKEN_RE = re.compile(r"^([1-9][0-9]{0,18})\.([A-Za-z0-9_-]{16,128})$")
# ``devices.id`` is a bigint: a larger number is not an unknown device but a value the database
# cannot even take as a parameter, so it is rejected here and answered 401 like any other token.
MAX_DEVICE_ID = 2**63 - 1


def hash_secret(secret: str) -> str:
    """Return the argon2id hash stored in ``enrollment_codes.code_hash``."""
    return _HASHER.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    """Check ``secret`` against an argon2 hash; a damaged or foreign hash is a mismatch.

    ``UnicodeEncodeError`` belongs in the list: argon2 encodes the stored hash as ASCII, so a
    value with a non-ASCII character in it raises before the library ever looks at it. A row
    the API cannot read is a refusal like any other, never a 500 in the authentication path.
    """
    try:
        return _HASHER.verify(hashed, secret)
    except (Argon2Error, InvalidHashError, UnicodeEncodeError):
        return False


async def hash_secret_async(secret: str) -> str:
    """``hash_secret`` off the event loop: issuing an installation code costs argon2."""
    return await _off_loop(lambda: hash_secret(secret))


async def verify_secret_async(secret: str, hashed: str) -> bool:
    """``verify_secret`` off the event loop: registration checks the code with argon2."""
    return await _off_loop(lambda: verify_secret(secret, hashed))


def encode_id(value: int, length: int) -> str:
    """Row id as ``length`` base32 characters, most significant first."""
    if value < 0 or value >= 32**length:
        raise ValueError(f"идентификатор {value} не помещается в {length} символов")
    digits = []
    for _ in range(length):
        value, index = divmod(value, 32)
        digits.append(CODE_ALPHABET[index])
    return "".join(reversed(digits))


def decode_id(text: str) -> int:
    """Inverse of ``encode_id``; the caller has already matched the alphabet."""
    value = 0
    for char in text:
        value = value * 32 + CODE_ALPHABET.index(char)
    return value


def new_enrollment_secret() -> str:
    """Random part of an installation code: 10 base32 characters, 50 bits."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(ENROLLMENT_SECRET_LENGTH))


def format_enrollment_code(code_id: int, secret: str) -> str:
    """Code shown to a human once: ``VKO-<id>-<secret>``; only its hash is stored."""
    groups = f"{encode_id(code_id, ENROLLMENT_ID_LENGTH)}-{secret[:5]}-{secret[5:]}"
    return f"{ENROLLMENT_CODE_PREFIX}-{groups}"


def parse_enrollment_code(code: str) -> tuple[int, str] | None:
    """Split a typed code into the row id and the secret; ``None`` when it is not a code."""
    prefix, _, rest = "".join(code.upper().split()).partition("-")
    if prefix != ENROLLMENT_CODE_PREFIX:
        return None
    match = ENROLLMENT_CODE_RE.match(rest.translate(CODE_ALIASES))
    if match is None:
        return None
    return decode_id(match[1]), match[2] + match[3]


def new_device_secret() -> str:
    """Random part of a device token."""
    return secrets.token_urlsafe(DEVICE_SECRET_BYTES)


def format_device_token(device_id: int, secret: str) -> str:
    """Token the agent sends in ``Authorization: Device <token>`` (ADR-005)."""
    return f"{device_id}.{secret}"


def parse_device_token(token: str) -> tuple[int, str] | None:
    """Split a token into the device id and the secret; ``None`` when it is not a token."""
    match = DEVICE_TOKEN_RE.match(token)
    if match is None:
        return None
    device_id = int(match[1])
    if device_id > MAX_DEVICE_ID:
        return None
    return device_id, match[2]


# A password reset link (T-65) carries a secret of the same family as a device token: 256 random
# bits with the id of its own row in front, stored as sha256 by ``hash_token`` and checked by
# ``verify_token``. These are those functions under the words of that use, not a second scheme.
new_reset_secret = new_device_secret
format_reset_token = format_device_token
parse_reset_token = parse_device_token


# Marks the algorithm of ``devices.token_hash``: what does not start with it is an argon2 hash
# handed out before the two families were split apart.
TOKEN_HASH_PREFIX = "sha256$"


def hash_token(secret: str) -> str:
    """Hash of a device token for ``devices.token_hash``: ``sha256$`` and 64 hex characters.

    No salt and no holding cost: the secret is 256 random bits (``new_device_secret``), so
    there is no dictionary to precompute against it and nothing to slow down. What a salt
    protects — two rows with the same secret looking alike — cannot happen when every row has
    its own random token.
    """
    return TOKEN_HASH_PREFIX + hashlib.sha256(secret.encode()).hexdigest()


def token_needs_rehash(hashed: str) -> bool:
    """True for a token hash still in the argon2 format, which costs argon2 to check.

    The caller replaces it with ``hash_token`` after a successful check: the token itself is
    never stored, so this is the only moment the server holds it (``app/core/deps.py``).
    """
    return not hashed.startswith(TOKEN_HASH_PREFIX)


def _token_hash_matches(secret: str, hashed: str) -> bool:
    """Compare a ``sha256$`` hash with the one ``secret`` makes; a damaged value is a mismatch.

    The comparison is on bytes, and that is the whole point of the encode. ``compare_digest``
    refuses two ``str`` with a character outside ASCII in them: it raises ``TypeError``
    instead of answering, and the value being compared comes straight out of the database. A
    row the API cannot read is a refusal like any other, never a 500 in the authentication
    path — the same rule ``verify_secret`` follows for an argon2 hash it cannot parse.

    Two hashes of this format have the same length, so the comparison tells nothing by how
    long it took: neither how many characters matched nor that anything matched at all.
    """
    try:
        stored = hashed.encode("ascii")
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(stored, hash_token(secret).encode("ascii"))


def verify_token(secret: str, hashed: str) -> bool:
    """Check a device token against ``devices.token_hash``, in either format.

    A damaged or foreign value is a mismatch, never an exception — in both formats.
    """
    if token_needs_rehash(hashed):
        return verify_secret(secret, hashed)
    return _token_hash_matches(secret, hashed)


async def verify_token_async(secret: str, hashed: str) -> bool:
    """``verify_token`` for async code: threads only the old format, which costs argon2.

    The new format stays in the event loop on purpose — sha256 of 43 characters is microseconds
    and handing it to a thread would cost more than computing it.
    """
    if token_needs_rehash(hashed):
        return await _off_loop(lambda: verify_secret(secret, hashed))
    return _token_hash_matches(secret, hashed)


def hash_password(password: str) -> str:
    """argon2id hash of a panel password for ``users.password_hash``."""
    return _HASHER.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Check a typed password; a damaged hash is a mismatch."""
    return verify_secret(password, hashed)


def password_needs_rehash(hashed: str) -> bool:
    """True when the hash was made with older parameters: login stores a fresh one."""
    return _HASHER.check_needs_rehash(hashed)


@lru_cache
def _dummy_password_hash() -> str:
    return _HASHER.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the time of a password check for an unknown e-mail: the answer time must not
    tell which e-mails have accounts."""
    verify_secret(password, _dummy_password_hash())


async def hash_password_async(password: str) -> str:
    """``hash_password`` off the event loop: creating a user and resetting a password."""
    return await _off_loop(lambda: hash_password(password))


async def verify_password_async(password: str, hashed: str) -> bool:
    """``verify_password`` off the event loop: every sign-in into the panel."""
    return await _off_loop(lambda: verify_password(password, hashed))


async def burn_password_check_async(password: str) -> None:
    """``burn_password_check`` off the event loop: it costs the same argon2 on purpose."""
    await _off_loop(lambda: burn_password_check(password))


type TokenType = Literal["access", "refresh"]


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode()


JWT_HEADER = _b64encode(_json({"alg": "HS256", "typ": "JWT"}))


def _signature(signing_input: str, key: str) -> bytes:
    return hmac.new(key.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()


def encode_jwt(
    *,
    user_id: int,
    version: int,
    typ: TokenType,
    issued_at: datetime,
    expires_at: datetime,
    key: str,
) -> str:
    """Signed token of a panel user; ``version`` is ``users.token_version`` at issue time."""
    claims = {
        "sub": str(user_id),
        "ver": version,
        "typ": typ,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    signing_input = f"{JWT_HEADER}.{_b64encode(_json(claims))}"
    return f"{signing_input}.{_b64encode(_signature(signing_input, key))}"


def decode_jwt(token: str, *, typ: TokenType, now: datetime, key: str) -> tuple[int, int] | None:
    """``(user_id, version)`` of a valid unexpired token of type ``typ``; ``None`` otherwise."""
    header, _, rest = token.partition(".")
    payload, _, signature = rest.partition(".")
    if header != JWT_HEADER or not payload or not signature:
        return None
    try:
        given = _b64decode(signature)
        claims = json.loads(_b64decode(payload))
    except (binascii.Error, ValueError):
        return None
    if not hmac.compare_digest(given, _signature(f"{header}.{payload}", key)):
        return None
    if not isinstance(claims, dict) or claims.get("typ") != typ:
        return None
    subject, version, expires = claims.get("sub"), claims.get("ver"), claims.get("exp")
    if not isinstance(subject, str) or not subject.isdecimal() or len(subject) > 18:
        return None
    if not isinstance(version, int) or not isinstance(expires, int):
        return None
    if expires <= now.timestamp():
        return None
    return int(subject), version
