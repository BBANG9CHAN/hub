from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
import typer

from hub.adapters.git_adapter import GitAdapter
from hub.adapters.wordpress_adapter import WordPressAdapter
from hub.core.logger import configure_logging
from hub.core.registry import registry
from hub.services.markdown_service import MarkdownService
from hub.workflows.blog_publish import BlogPublishWorkflow

app = typer.Typer(help="hub — 개인 자동화 허브 CLI")
logger = structlog.get_logger(__name__)


@app.command()
def publish(
    filepath: Path = typer.Argument(..., help="발행할 마크다운 파일 경로"),
    log_level: str = typer.Option("INFO", "--log-level", help="로그 레벨"),
) -> None:
    """마크다운 포스트를 blog 리포에 커밋하고 WordPress에 발행."""
    configure_logging(log_level)
    asyncio.run(_run_publish(filepath))


async def _run_publish(filepath: Path) -> None:
    git = GitAdapter()
    wp = WordPressAdapter()

    registry.register(git)
    registry.register(wp)

    await registry.start_all()
    try:
        markdown = MarkdownService()
        workflow = BlogPublishWorkflow(git=git, wordpress=wp, markdown=markdown)
        result = await workflow.run(filepath)
        typer.echo(f"발행 완료: {result['title']}")
        typer.echo(f"URL: {result['url']}")
    finally:
        await registry.stop_all()
