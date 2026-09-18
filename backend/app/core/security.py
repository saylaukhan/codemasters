"""Secrets the API checks: device tokens, installation codes, passwords and panel JWTs.

Neither secret is stored: the database keeps only their argon2id hash — ``devices.token_hash``
and ``enrollment_codes.code_hash``. An argon2 hash carries a random salt, so no row can be
found by hashing what the client sent; every secret therefore starts with the id of its own
row (``17.<random>`` for a token, ``VKO-0011-...`` for a code). The id selects exactly one row
and argon2 checks the random part, so a wrong id is as useless as a wrong secret.

Parameters are the argon2id minimum recommended by OWASP (19 MiB, 2 passes, 1 lane); the same
hasher stores passwords of the panel users (``users.password_hash``, ТЗ п. 12).

Panel JWTs (ADR-009) are HS256 signed with ``SECRET_KEY``: access for 15 minutes, refresh in
the httpOnly cookie. Only the header this module writes is accepted, so a token cannot choose
its own algorithm; ``typ`` keeps a refresh token out of ``Authorization`` and back.
"""

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)

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
    """Return the argon2id hash stored in ``token_hash`` / ``code_hash``."""
    return _HASHER.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    """Check ``secret`` against a stored hash; a damaged or foreign hash is a mismatch."""
    try:
        return _HASHER.verify(hashed, secret)
    except (Argon2Error, InvalidHashError):
        return False


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
