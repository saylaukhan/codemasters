"""Ollama — the provider of a closed loop, without an external API and without a key (ADR-011).

The customer may require a contour without external services: the model then runs next to the
server and answers at ``POST /api/generate``. The address is a variable of the environment; a
key does not exist here, so there is nothing to mask.
"""

from typing import Any

from app.services.llm.base import HttpLLMProvider

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"


class OllamaProvider(HttpLLMProvider):
    """Draft of an appeal through a model of a closed loop."""

    name = "ollama"

    def __init__(self, base_url: str = "", model: str = "") -> None:
        super().__init__()
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        # ``stream: false`` — one answer as one object; the panel does not show the typing.
        payload: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        body = await self.post(f"{self.base_url}/api/generate", payload, {})
        answer = body.get("response")
        if not isinstance(answer, str) or not answer.strip():
            raise self.unavailable("в ответе нет текста")
        return answer.strip()
