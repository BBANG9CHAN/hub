from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

import structlog

from hub.core.bus import bus
from hub.services.claude_service import ClaudeService

logger = structlog.get_logger(__name__)


class DraftPostWorkflow:
    def __init__(
        self,
        *,
        claude: ClaudeService,
        output_dir: Path | None = None,
    ) -> None:
        self._claude = claude
        self._output_dir = output_dir or Path("drafts")

    async def run(self, topic: str, notes: str) -> dict[str, Any]:
        logger.info("draft_post.start", topic=topic)

        draft_text = await self._claude.generate_blog_draft(topic, notes)
        title = _extract_title(draft_text) or topic

        date_str = datetime.date.today().isoformat()
        slug = _slugify(topic)
        filename = f"{date_str}-{slug}.md"

        self._output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._output_dir / filename
        out_path.write_text(draft_text, encoding="utf-8")

        await bus.publish("draft.created", {"path": str(out_path), "title": title})

        logger.info("draft_post.done", path=str(out_path), title=title)
        return {"path": str(out_path), "title": title}


def _extract_title(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "draft"
