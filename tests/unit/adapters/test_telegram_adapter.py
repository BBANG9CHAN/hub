from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hub.adapters.telegram_adapter import TelegramAdapter
from hub.core.bus import EventBus


@pytest.fixture
def mock_app() -> MagicMock:
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(username="test_bot")

    updater = AsyncMock()
    updater.running = False

    app = MagicMock()
    app.bot = bot
    app.updater = updater
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.stop = AsyncMock()
    app.shutdown = AsyncMock()
    app.add_handler = MagicMock()
    return app


def _build_patches(mock_app: MagicMock, test_bus: EventBus) -> tuple[Any, Any]:
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    p_app = patch("hub.adapters.telegram_adapter.Application")
    p_bus = patch("hub.adapters.telegram_adapter.bus", test_bus)
    return p_app, p_bus


async def test_name() -> None:
    with patch("hub.adapters.telegram_adapter.get_settings") as mock_settings:
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"
        adapter = TelegramAdapter()
    assert adapter.name == "telegram"


async def test_start_initialises_app_and_subscribes(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()

    assert adapter._app is mock_app
    mock_app.initialize.assert_awaited_once()
    mock_app.start.assert_awaited_once()
    mock_app.updater.start_polling.assert_awaited_once_with(drop_pending_updates=True)
    assert len(test_bus._subscribers["post.published"]) == 1
    assert len(test_bus._subscribers["error.occurred"]) == 1


async def test_stop_unsubscribes_and_shuts_down(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app
    mock_app.updater.running = True

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()
        await adapter.stop()

    assert adapter._app is None
    mock_app.updater.stop.assert_awaited_once()
    mock_app.stop.assert_awaited_once()
    mock_app.shutdown.assert_awaited_once()
    assert len(test_bus._subscribers["post.published"]) == 0
    assert len(test_bus._subscribers["error.occurred"]) == 0


async def test_healthcheck_true_when_started(mock_app: MagicMock) -> None:
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus"),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()
        result = await adapter.healthcheck()

    assert result is True


async def test_healthcheck_false_when_not_started() -> None:
    with patch("hub.adapters.telegram_adapter.get_settings") as mock_settings:
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"
        adapter = TelegramAdapter()
    assert await adapter.healthcheck() is False


async def test_send_message_calls_bot(mock_app: MagicMock) -> None:
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus"),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()
        await adapter.send_message("테스트 메시지")

    mock_app.bot.send_message.assert_awaited_once_with(chat_id="123", text="테스트 메시지")


async def test_send_message_raises_when_not_started() -> None:
    with patch("hub.adapters.telegram_adapter.get_settings") as mock_settings:
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"
        adapter = TelegramAdapter()
    with pytest.raises(RuntimeError, match="not started"):
        await adapter.send_message("msg")


async def test_on_command_publishes_event(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("telegram.command_received", capture)

    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()

        message = MagicMock()
        message.chat_id = 123
        message.text = "/publish posts/foo.md"
        message.from_user = None
        update = MagicMock()
        update.message = message

        await adapter._on_command(update, MagicMock())

    assert len(captured) == 1
    event, payload = captured[0]
    assert event == "telegram.command_received"
    assert payload["command"] == "publish"
    assert payload["args"] == "posts/foo.md"
    assert payload["chat_id"] == "123"


async def test_on_command_ignores_unauthorized_chat(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("telegram.command_received", capture)

    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()

        message = MagicMock()
        message.chat_id = 999  # 다른 chat_id
        message.text = "/publish posts/foo.md"
        update = MagicMock()
        update.message = message

        await adapter._on_command(update, MagicMock())

    assert len(captured) == 0


async def test_on_post_published_sends_message(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()
        await adapter._on_post_published(
            "post.published",
            {"title": "테스트 포스트", "url": "https://example.com/post/1"},
        )

    call_args = mock_app.bot.send_message.call_args
    assert "테스트 포스트" in call_args.kwargs["text"]
    assert "https://example.com/post/1" in call_args.kwargs["text"]


async def test_on_error_occurred_sends_message(mock_app: MagicMock) -> None:
    test_bus = EventBus()
    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    with (
        patch("hub.adapters.telegram_adapter.Application") as mock_app_cls,
        patch("hub.adapters.telegram_adapter.bus", test_bus),
        patch("hub.adapters.telegram_adapter.get_settings") as mock_settings,
    ):
        mock_app_cls.builder.return_value = mock_builder
        mock_settings.return_value.telegram.token = "tok"
        mock_settings.return_value.telegram.chat_id = "123"

        adapter = TelegramAdapter()
        await adapter.start()
        await adapter._on_error_occurred("error.occurred", {"message": "뭔가 잘못됨"})

    call_args = mock_app.bot.send_message.call_args
    assert "[오류]" in call_args.kwargs["text"]
    assert "뭔가 잘못됨" in call_args.kwargs["text"]
