from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from hub.adapters.git_adapter import GitAdapter
from hub.adapters.wordpress_adapter import WordPressAdapter
from hub.core.bus import bus
from hub.services.markdown_service import MarkdownService
from hub.workflows.blog_publish import BlogPublishWorkflow

if TYPE_CHECKING:
    from hub.adapters.telegram_adapter import TelegramAdapter
    from hub.core.registry import AdapterRegistry

logger = structlog.get_logger(__name__)

_HELP_TEXT = (
    "사용 가능한 명령어\n"
    "/status — 시스템 상태 확인\n"
    "/publish <경로> — 마크다운 포스트 발행\n"
    "/help — 도움말"
)


class RemoteControlWorkflow:
    def __init__(
        self,
        *,
        telegram: TelegramAdapter,
        git: GitAdapter,
        wordpress: WordPressAdapter,
        markdown: MarkdownService,
        registry: AdapterRegistry,
    ) -> None:
        self._telegram = telegram
        self._git = git
        self._wp = wordpress
        self._markdown = markdown
        self._registry = registry

    async def start(self) -> None:
        bus.subscribe("telegram.command_received", self._handle_command)
        logger.info("remote_control.started")

    async def stop(self) -> None:
        bus.unsubscribe("telegram.command_received", self._handle_command)
        logger.info("remote_control.stopped")

    async def _handle_command(self, event: str, payload: Any) -> None:
        command: str = payload.get("command", "")
        args: str = payload.get("args", "")
        logger.info("remote_control.command", command=command, args=args)

        try:
            match command:
                case "status":
                    await self._cmd_status()
                case "publish":
                    await self._cmd_publish(args)
                case "help":
                    await self._telegram.send_message(_HELP_TEXT)
                case _:
                    await self._telegram.send_message(
                        f"알 수 없는 명령어: /{command}\n/help 로 도움말 확인"
                    )
        except Exception as exc:
            logger.error("remote_control.command_error", command=command, error=str(exc), exc_info=exc)
            await bus.publish("error.occurred", {"message": f"[{command}] {exc}"})

    async def _cmd_status(self) -> None:
        results = await self._registry.healthcheck_all()
        if not results:
            await self._telegram.send_message("등록된 어댑터 없음")
            return
        lines = [("✅" if ok else "❌") + f" {name}" for name, ok in results.items()]
        await self._telegram.send_message("시스템 상태\n" + "\n".join(lines))

    async def _cmd_publish(self, args: str) -> None:
        path = args.strip()
        if not path:
            await self._telegram.send_message("사용법: /publish <파일경로>")
            return
        try:
            workflow = BlogPublishWorkflow(
                git=self._git,
                wordpress=self._wp,
                markdown=self._markdown,
            )
            await workflow.run(path)
            # post.published 이벤트가 발행되어 TelegramAdapter가 자동으로 완료 알림 전송
        except FileNotFoundError as exc:
            await self._telegram.send_message(f"[발행 오류] 파일을 찾을 수 없습니다: {path}")
            logger.warning("remote_control.publish_file_not_found", path=path, error=str(exc))
        except Exception as exc:
            await self._telegram.send_message(f"[발행 오류] {exc}")
            logger.error("remote_control.publish_error", path=path, error=str(exc), exc_info=exc)
