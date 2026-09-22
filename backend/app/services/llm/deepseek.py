"""DeepSeek — a provider of a draft through the Chat Completions API (ADR-011, T-83).

DeepSeek speaks the wire format of OpenAI: ``POST /chat/completions`` takes a list of
messages with the system prompt as the first of them and answers with ``choices``; the text of
the draft is ``message.content`` of the first one. The key goes into the ``Authorization``
header as a bearer token and nowhere else: the base class masks it in everything that leaves
this module.

``deepseek-reasoner`` answers in the same shape and keeps its reasoning in a separate field
``reasoning_content``, which the draft does not need: only ``content`` becomes the letter. Any
service compatible with OpenAI speaks the same shape, so ``LLM_URL`` may point this class at
one of them — for example at a model of a closed loop behind vLLM.
"""

from typing import Any

from app.services.llm.base import MAX_OUTPUT_TOKENS, HttpLLMProvider

DEEPSEEK_API = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def text_of(body: dict[str, Any]) -> str:
    """Text of the first choice of one answer; raises when the answer has no text in it."""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("в ответе нет choices")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("в ответе нет текста")
    return content.strip()


class DeepSeekProvider(HttpLLMProvider):
    """Draft of an appeal through the Chat Completions API of DeepSeek."""

    name = "deepseek"

    def __init__(self, api_key: str, model: str = "", base_url: str = "") -> None:
        super().__init__(api_key)
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or DEEPSEEK_API).rstrip("/")

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        # ``stream: false`` — one answer as one object, as with Ollama.
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "stream": False,
        }
        body = await self.post(
            f"{self.base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {self._secret}"},
        )
        try:
            return text_of(body)
        except (KeyError, TypeError, ValueError) as error:
            raise self.unavailable(str(error)) from error
