from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import structlog
import typer

from hub.adapters.git_adapter import GitAdapter
from hub.adapters.telegram_adapter import TelegramAdapter
from hub.adapters.wordpress_adapter import WordPressAdapter
from hub.core.logger import configure_logging
from hub.core.registry import registry
from hub.services.claude_service import ClaudeService
from hub.services.markdown_service import MarkdownService
from hub.workflows.blog_publish import BlogPublishWorkflow
from hub.workflows.draft_post import DraftPostWorkflow
from hub.workflows.remote_control import RemoteControlWorkflow

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


@app.command()
def draft(
    from_file: Path = typer.Option(..., "--from", help="경험 노트 파일 경로"),
    topic: str = typer.Option(..., "--topic", help="포스트 주제"),
    output_dir: Path = typer.Option(Path("drafts"), "--output-dir", help="초안 저장 디렉토리"),
    log_level: str = typer.Option("INFO", "--log-level", help="로그 레벨"),
) -> None:
    """경험 노트와 주제로 블로그 초안을 생성한다."""
    configure_logging(log_level)
    asyncio.run(_run_draft(from_file, topic, output_dir))


async def _run_draft(from_file: Path, topic: str, output_dir: Path) -> None:
    if not from_file.exists():
        typer.echo(f"오류: 파일을 찾을 수 없습니다: {from_file}", err=True)
        raise typer.Exit(1)

    notes = from_file.read_text(encoding="utf-8")
    claude = ClaudeService()
    workflow = DraftPostWorkflow(claude=claude, output_dir=output_dir)
    result = await workflow.run(topic, notes)
    typer.echo(f"초안 생성 완료: {result['title']}")
    typer.echo(f"경로: {result['path']}")


@app.command()
def daemon(
    log_level: str = typer.Option("INFO", "--log-level", help="로그 레벨"),
) -> None:
    """Telegram 폴링을 시작하고 원격 제어 명령을 수신한다."""
    configure_logging(log_level)
    asyncio.run(_run_daemon())


async def _run_daemon() -> None:
    git = GitAdapter()
    wp = WordPressAdapter()
    telegram = TelegramAdapter()
    markdown = MarkdownService()

    registry.register(git)
    registry.register(wp)
    registry.register(telegram)

    remote_control = RemoteControlWorkflow(
        telegram=telegram,
        git=git,
        wordpress=wp,
        markdown=markdown,
        registry=registry,
    )

    await registry.start_all()
    await remote_control.start()

    logger.info("daemon.started")
    typer.echo("허브 데몬 시작됨. Ctrl+C로 종료.")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    await stop_event.wait()

    logger.info("daemon.stopping")
    await remote_control.stop()
    await registry.stop_all()
    typer.echo("허브 데몬 종료됨.")
