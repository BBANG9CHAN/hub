from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from hub.adapters.git_adapter import GitAdapter
from hub.adapters.wordpress_adapter import WordPressAdapter
from hub.core.bus import bus
from hub.services.markdown_service import MarkdownService

logger = structlog.get_logger(__name__)


class BlogPublishWorkflow:
    def __init__(
        self,
        *,
        git: GitAdapter,
        wordpress: WordPressAdapter,
        markdown: MarkdownService,
    ) -> None:
        self._git = git
        self._wp = wordpress
        self._markdown = markdown

    async def run(self, filepath: str | Path) -> dict[str, Any]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Post file not found: {path}")

        md_content = path.read_text(encoding="utf-8")
        title = _extract_title(md_content) or path.stem

        logger.info("blog_publish.start", filepath=str(path), title=title)

        # 1. blog 리포에 커밋/푸시
        await self._git.commit_and_push(str(path), f"publish: {path.name}")

        # 2. MD → WP 블록 변환
        wp_content = await self._markdown.to_wp_blocks(md_content)

        # 3. WordPress에 발행
        wp_result = await self._wp.create_post(title=title, content=wp_content)

        # 4. 후속 어댑터(Telegram 등) 트리거
        await bus.publish(
            "post.published",
            {"post_id": wp_result["id"], "url": wp_result["url"], "title": title},
        )

        logger.info("blog_publish.done", post_id=wp_result["id"], url=wp_result["url"])
        return {"post_id": wp_result["id"], "url": wp_result["url"], "title": title}


def _extract_title(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None
