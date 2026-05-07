from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from anthropic.types import TextBlock
from tenacity import retry, stop_after_attempt, wait_exponential

from hub.core.config import get_settings

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


class ClaudeService:
    def __init__(self, api_key: str | None = None) -> None:
        cfg = get_settings().claude
        self._client = AsyncAnthropic(api_key=api_key or cfg.api_key)
        self._model = cfg.model
        self._max_tokens = cfg.max_tokens

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if system:
            kwargs["system"] = system
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        logger.info(
            "claude.generated",
            model=self._model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
        content = message.content[0]
        if not isinstance(content, TextBlock):
            raise ValueError(f"Expected TextBlock, got {type(content).__name__}")
        return content.text

    async def generate_blog_draft(self, topic: str, notes: str) -> str:
        system = _load_prompt("blog_post_generation.md")
        return await self.generate(f"Topic: {topic}\n\nNotes:\n{notes}", system=system)


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
