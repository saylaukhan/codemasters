"""One adapter between the appeals and any large language model (T-46, ТЗ п. 17, ADR-011).

The appeals know one method: text by a prompt. Which model answers — Claude API over the
network or Ollama in a closed loop — is a setting of the environment, not a branch in the
business logic, so a new model is a new class here and nothing else (ADR-011).

Two rules hold for every implementation. A model that does not answer must not become a 500:
the error leaves as ``application/problem+json`` with status 503 (ADR-009), and the editor of
T-47 opens with an empty template instead of an error across the whole screen. And the key
never leaves the environment: it is not written to the log, not put into the ``detail`` of the
answer and not shown by ``repr`` — everything that goes out of here passes through ``redact``.

The request itself is ``urllib`` in a thread, as in ``app/services/notifications.py``: the
outgoing channels of this server are stdlib, and an HTTP client is not worth a dependency.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from app.core.errors import ApiError

logger = logging.getLogger(__name__)

# A draft is waited for by a person in front of the panel: a model slower than this has failed,
# not slowed down. The editor of T-47 opens empty and the text is written by hand (ADR-011).
REQUEST_TIMEOUT_S = 60
# An official letter of a page and a half; the context is collected by the server (T-47).
MAX_OUTPUT_TOKENS = 2000

# Stable ``type`` codes of the problem+json of this service (ADR-009).
NOT_CONFIGURED = "llm_not_configured"
UNAVAILABLE = "llm_unavailable"

SECRET_MASK = "***"
NO_DRAFT = "Черновик не создан, напишите текст обращения вручную."


def request_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """One POST of JSON and the object it answered; raises on anything but a JSON object."""
    request = urllib.request.Request(  # noqa: S310 — the address comes from the environment
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:  # noqa: S310
        body: Any = json.loads(response.read())
    if not isinstance(body, dict):
        raise ValueError("ответ модели — не объект JSON")
    return body


def not_configured(detail: str) -> ApiError:
    """Error of an installation without a model: 503 with a reason a person can act on."""
    return ApiError(503, NOT_CONFIGURED, detail)


class LLMProvider(ABC):
    """Text generation by a prompt — the only thing the appeals know about a model."""

    name: str

    @abstractmethod
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Text of the model by ``prompt``; ``ApiError`` 503 when the model cannot answer."""

    def __repr__(self) -> str:
        # No key and no address: a repr of a provider ends up in tracebacks and logs.
        return f"<{type(self).__name__} name={self.name}>"


class HttpLLMProvider(LLMProvider):
    """A model behind an HTTP API: the shared request, the shared masking of the key."""

    def __init__(self, secret: str = "") -> None:
        self._secret = secret

    def redact(self, text: str) -> str:
        """``text`` without the key: nothing that leaves this class may carry a secret."""
        if self._secret:
            return text.replace(self._secret, SECRET_MASK)
        return text

    def unavailable(self, reason: str) -> ApiError:
        """Error of an unreachable model: the same masked reason in the log and in the answer."""
        safe = self.redact(reason)
        logger.warning("LLM %s не ответил: %s", self.name, safe)
        return ApiError(503, UNAVAILABLE, f"Модель недоступна ({safe}). {NO_DRAFT}")

    async def post(
        self, url: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Answer of the model as an object; every network failure becomes ``ApiError`` 503."""
        try:
            return await asyncio.to_thread(request_json, url, payload, headers)
        except urllib.error.HTTPError as error:
            # The body of the answer may quote the request: only the status goes further.
            raise self.unavailable(f"HTTP {error.code}") from error
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise self.unavailable(str(error) or type(error).__name__) from error
