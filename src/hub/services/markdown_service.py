from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class MarkdownService:
    # TODO: markdown → WordPress Gutenberg 블록 JSON 변환 구현
    async def to_wp_blocks(self, content: str) -> str:
        logger.debug("markdown.convert", chars=len(content))
        return content
