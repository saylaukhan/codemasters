"""Claude API — the provider of a draft by default (ADR-011, T-46).

The Messages API answers with a list of blocks; a draft is their text glued together. The key
goes into the ``x-api-key`` header and nowhere else: the base class masks it in everything that
leaves this module.
"""

from typing import Any

from app.services.llm.base import MAX_OUTPUT_TOKENS, HttpLLMProvider

CLAUDE_API = "https://api.anthropic.com"
# Version of the wire format of the Messages API — not the version of the model.
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-5"


def text_of(body: dict[str, Any]) -> str:
    """Text blocks of one answer glued together; raises when the answer has none of them."""
    blocks = body.get("content")
    if not isinstance(blocks, list):
        raise ValueError("в ответе нет content")
    parts = [
        block["text"]
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text" and "text" in block
    ]
    if not parts:
        raise ValueError("в ответе нет текста")
    return "".join(parts).strip()


class ClaudeProvider(HttpLLMProvider):
    """Draft of an appeal through the Messages API of Claude."""

    name = "claude"

    def __init__(self, api_key: str, model: str = "", base_url: str = "") -> None:
        super().__init__(api_key)
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or CLAUDE_API).rstrip("/")

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        body = await self.post(
            f"{self.base_url}/v1/messages",
            payload,
            {"x-api-key": self._secret, "anthropic-version": ANTHROPIC_VERSION},
        )
        try:
            return text_of(body)
        except (KeyError, TypeError, ValueError) as error:
            raise self.unavailable(str(error)) from error
