from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hub.core.bus import EventBus
from hub.workflows.blog_publish import BlogPublishWorkflow, _extract_title

_WP_RESULT = {"id": 42, "url": "https://example.com/?p=42"}


def _make_workflow() -> tuple[BlogPublishWorkflow, AsyncMock, AsyncMock, AsyncMock]:
    git = AsyncMock()
    wp = AsyncMock()
    wp.create_post.return_value = _WP_RESULT
    markdown = AsyncMock()
    markdown.to_wp_blocks.return_value = "<p>content</p>"
    workflow = BlogPublishWorkflow(git=git, wordpress=wp, markdown=markdown)
    return workflow, git, wp, markdown


# ── _extract_title ────────────────────────────────────────────────────────────

def test_extract_title_from_h1() -> None:
    assert _extract_title("# My Title\n\ncontent") == "My Title"


def test_extract_title_strips_whitespace() -> None:
    assert _extract_title("#   Padded  \n") == "Padded"


def test_extract_title_none_when_no_h1() -> None:
    assert _extract_title("no heading\ncontent") is None


def test_extract_title_ignores_h2() -> None:
    assert _extract_title("## Section\ncontent") is None


# ── run() — happy path ────────────────────────────────────────────────────────

async def test_run_returns_expected_result(tmp_path: Path) -> None:
    post = tmp_path / "hello.md"
    post.write_text("# Hello World\n\ncontent", encoding="utf-8")

    workflow, _, _, _ = _make_workflow()
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        result = await workflow.run(post)

    assert result == {"post_id": 42, "url": "https://example.com/?p=42", "title": "Hello World"}


async def test_run_uses_stem_as_title_when_no_h1(tmp_path: Path) -> None:
    post = tmp_path / "my-post.md"
    post.write_text("no heading here", encoding="utf-8")

    workflow, _, _, _ = _make_workflow()
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        result = await workflow.run(post)

    assert result["title"] == "my-post"


# ── run() — adapter/service calls ────────────────────────────────────────────

async def test_run_calls_git_commit_and_push(tmp_path: Path) -> None:
    post = tmp_path / "foo.md"
    post.write_text("# Foo\n\ncontent", encoding="utf-8")

    workflow, git, _, _ = _make_workflow()
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        await workflow.run(post)

    git.commit_and_push.assert_awaited_once_with(str(post), "publish: foo.md")


async def test_run_calls_markdown_convert(tmp_path: Path) -> None:
    post = tmp_path / "bar.md"
    content = "# Bar\n\nbody text"
    post.write_text(content, encoding="utf-8")

    workflow, _, _, markdown = _make_workflow()
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        await workflow.run(post)

    markdown.to_wp_blocks.assert_awaited_once_with(content)


async def test_run_calls_wp_create_post_with_converted_content(tmp_path: Path) -> None:
    post = tmp_path / "baz.md"
    post.write_text("# Baz\n\nbody", encoding="utf-8")

    workflow, _, wp, markdown = _make_workflow()
    markdown.to_wp_blocks.return_value = "<p>body</p>"
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        await workflow.run(post)

    wp.create_post.assert_awaited_once_with(title="Baz", content="<p>body</p>")


# ── run() — event publishing ──────────────────────────────────────────────────

async def test_run_publishes_post_published_event(tmp_path: Path) -> None:
    post = tmp_path / "ev.md"
    post.write_text("# Event Test\n\nbody", encoding="utf-8")

    workflow, _, _, _ = _make_workflow()
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("post.published", capture)

    with patch("hub.workflows.blog_publish.bus", test_bus):
        await workflow.run(post)

    assert len(captured) == 1
    event, payload = captured[0]
    assert event == "post.published"
    assert payload["post_id"] == 42
    assert payload["url"] == "https://example.com/?p=42"
    assert payload["title"] == "Event Test"


# ── run() — error cases ───────────────────────────────────────────────────────

async def test_run_raises_for_missing_file(tmp_path: Path) -> None:
    workflow, _, _, _ = _make_workflow()
    with pytest.raises(FileNotFoundError, match="not found"):
        await workflow.run(tmp_path / "nonexistent.md")


async def test_run_propagates_git_error(tmp_path: Path) -> None:
    post = tmp_path / "err.md"
    post.write_text("# Err\n\ncontent", encoding="utf-8")

    workflow, git, _, _ = _make_workflow()
    git.commit_and_push.side_effect = RuntimeError("repo not started")

    with pytest.raises(RuntimeError, match="repo not started"):
        await workflow.run(post)


async def test_run_propagates_wp_error(tmp_path: Path) -> None:
    post = tmp_path / "wperr.md"
    post.write_text("# WP Err\n\ncontent", encoding="utf-8")

    workflow, _, wp, _ = _make_workflow()
    wp.create_post.side_effect = RuntimeError("WP not available")
    test_bus = EventBus()

    with patch("hub.workflows.blog_publish.bus", test_bus):
        with pytest.raises(RuntimeError, match="WP not available"):
            await workflow.run(post)
