from __future__ import annotations

from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_fixed
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from hub.adapters.base import Adapter
from hub.core.bus import bus
from hub.core.config import get_settings

logger = structlog.get_logger(__name__)


class TelegramAdapter(Adapter):
    def __init__(self) -> None:
        cfg = get_settings().telegram
        self._token = cfg.token
        self._chat_id = cfg.chat_id
        self._app: Application | None = None  # type: ignore[type-arg]

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.COMMAND, self._on_command))

        bus.subscribe("post.published", self._on_post_published)
        bus.subscribe("error.occurred", self._on_error_occurred)

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram.started", chat_id=self._chat_id)

    async def stop(self) -> None:
        bus.unsubscribe("post.published", self._on_post_published)
        bus.unsubscribe("error.occurred", self._on_error_occurred)

        if self._app is not None:
            if self._app.updater.running:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None
        logger.info("telegram.stopped")

    async def healthcheck(self) -> bool:
        if self._app is None:
            return False
        try:
            me = await self._app.bot.get_me()
            return me is not None
        except Exception:
            return False

    async def send_message(self, text: str) -> None:
        if self._app is None:
            raise RuntimeError("TelegramAdapter not started")
        await self._send(text)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _send(self, text: str) -> None:
        await self._app.bot.send_message(chat_id=self._chat_id, text=text)  # type: ignore[union-attr]
        logger.info("telegram.message_sent", length=len(text))

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        if str(update.message.chat_id) != self._chat_id:
            logger.warning("telegram.unauthorized_command", chat_id=update.message.chat_id)
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        # /command@botname → strip @botname suffix
        command = parts[0].lstrip("/").split("@")[0]
        args = parts[1] if len(parts) > 1 else ""

        await bus.publish(
            "telegram.command_received",
            {
                "command": command,
                "args": args,
                "chat_id": str(update.message.chat_id),
            },
        )
        logger.info("telegram.command_received", command=command)

    async def _on_post_published(self, event: str, payload: Any) -> None:
        title = payload.get("title", "")
        url = payload.get("url", "")
        await self.send_message(f"새 포스트 발행: {title}\n{url}")

    async def _on_error_occurred(self, event: str, payload: Any) -> None:
        message = payload.get("message", str(payload))
        await self.send_message(f"[오류] {message}")
