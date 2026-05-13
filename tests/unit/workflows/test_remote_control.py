from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hub.core.bus import EventBus
from hub.workflows.remote_control import RemoteControlWorkflow


def _make_workflow(
    test_bus: EventBus | None = None,
) -> tuple[RemoteControlWorkflow, AsyncMock, AsyncMock]:
    telegram = AsyncMock()
    git = AsyncMock()
    wp = AsyncMock()
    wp.create_post.return_value = {"id": 1, "url": "https://example.com/?p=1"}
    markdown = AsyncMock()
    markdown.to_wp_blocks.return_value = "<p>content</p>"

    mock_registry = MagicMock()
    mock_registry.healthcheck_all = AsyncMock(return_value={"telegram": True, "git": True})

    workflow = RemoteControlWorkflow(
        telegram=telegram,
        git=git,
        wordpress=wp,
        markdown=markdown,
        registry=mock_registry,
    )
    return workflow, telegram, mock_registry


# ── 생명주기 ──────────────────────────────────────────────────────────────────

async def test_start_subscribes_to_command_event() -> None:
    test_bus = EventBus()
    workflow, _, _ = _make_workflow()
    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow.start()
    assert len(test_bus._subscribers["telegram.command_received"]) == 1


async def test_stop_unsubscribes_from_command_event() -> None:
    test_bus = EventBus()
    workflow, _, _ = _make_workflow()
    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow.start()
        await workflow.stop()
    assert len(test_bus._subscribers["telegram.command_received"]) == 0


# ── /status ───────────────────────────────────────────────────────────────────

async def test_status_sends_healthcheck_results() -> None:
    test_bus = EventBus()
    workflow, telegram, mock_registry = _make_workflow()
    mock_registry.healthcheck_all.return_value = {"telegram": True, "git": False}

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command("telegram.command_received", {"command": "status", "args": ""})

    telegram.send_message.assert_awaited_once()
    text: str = telegram.send_message.call_args[0][0]
    assert "✅ telegram" in text
    assert "❌ git" in text


async def test_status_sends_no_adapters_message_when_empty() -> None:
    test_bus = EventBus()
    workflow, telegram, mock_registry = _make_workflow()
    mock_registry.healthcheck_all.return_value = {}

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command("telegram.command_received", {"command": "status", "args": ""})

    text: str = telegram.send_message.call_args[0][0]
    assert "등록된 어댑터 없음" in text


# ── /help ─────────────────────────────────────────────────────────────────────

async def test_help_sends_help_text() -> None:
    test_bus = EventBus()
    workflow, telegram, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command("telegram.command_received", {"command": "help", "args": ""})

    text: str = telegram.send_message.call_args[0][0]
    assert "/status" in text
    assert "/publish" in text
    assert "/help" in text


# ── /publish ──────────────────────────────────────────────────────────────────

async def test_publish_sends_usage_when_no_args() -> None:
    test_bus = EventBus()
    workflow, telegram, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command("telegram.command_received", {"command": "publish", "args": ""})

    text: str = telegram.send_message.call_args[0][0]
    assert "사용법" in text


async def test_publish_runs_blog_workflow_on_valid_file(tmp_path: Path) -> None:
    post = tmp_path / "hello.md"
    post.write_text("# Hello\n\ncontent", encoding="utf-8")

    test_bus = EventBus()
    workflow, telegram, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command(
            "telegram.command_received",
            {"command": "publish", "args": str(post)},
        )

    # 성공 시 telegram.send_message는 호출되지 않음
    # (post.published 이벤트를 통해 TelegramAdapter가 처리)
    telegram.send_message.assert_not_awaited()


async def test_publish_publishes_post_published_event_on_success(tmp_path: Path) -> None:
    post = tmp_path / "hello.md"
    post.write_text("# Hello\n\ncontent", encoding="utf-8")

    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("post.published", capture)

    workflow, _, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        with patch("hub.workflows.blog_publish.bus", test_bus):
            await workflow._handle_command(
                "telegram.command_received",
                {"command": "publish", "args": str(post)},
            )

    assert len(captured) == 1
    assert captured[0][0] == "post.published"


async def test_publish_sends_error_message_for_missing_file() -> None:
    test_bus = EventBus()
    workflow, telegram, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command(
            "telegram.command_received",
            {"command": "publish", "args": "/nonexistent/path/foo.md"},
        )

    text: str = telegram.send_message.call_args[0][0]
    assert "발행 오류" in text
    assert "파일을 찾을 수 없습니다" in text


# ── 알 수 없는 명령어 ──────────────────────────────────────────────────────────

async def test_unknown_command_sends_error_message() -> None:
    test_bus = EventBus()
    workflow, telegram, _ = _make_workflow()

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command(
            "telegram.command_received",
            {"command": "whatever", "args": ""},
        )

    text: str = telegram.send_message.call_args[0][0]
    assert "/whatever" in text
    assert "/help" in text


# ── 예외 처리 ─────────────────────────────────────────────────────────────────

async def test_command_error_publishes_error_event() -> None:
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("error.occurred", capture)

    workflow, _, mock_registry = _make_workflow()
    mock_registry.healthcheck_all.side_effect = RuntimeError("registry down")

    with patch("hub.workflows.remote_control.bus", test_bus):
        await workflow._handle_command(
            "telegram.command_received",
            {"command": "status", "args": ""},
        )

    assert len(captured) == 1
    assert captured[0][0] == "error.occurred"
    assert "status" in captured[0][1]["message"]
