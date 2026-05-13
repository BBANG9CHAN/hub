from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hub.core.bus import EventBus
from hub.workflows.draft_post import DraftPostWorkflow, _extract_title, _slugify

_DRAFT_TEXT = "# 삽질 기록\n\n본문 내용."


def _make_workflow(tmp_path: Path) -> tuple[DraftPostWorkflow, AsyncMock]:
    claude = AsyncMock()
    claude.generate_blog_draft.return_value = _DRAFT_TEXT
    workflow = DraftPostWorkflow(claude=claude, output_dir=tmp_path / "drafts")
    return workflow, claude


# ── _extract_title ────────────────────────────────────────────────────────────

def test_extract_title_h1() -> None:
    assert _extract_title("# 제목\n\n본문") == "제목"


def test_extract_title_strips_whitespace() -> None:
    assert _extract_title("#   공백 제목  \n") == "공백 제목"


def test_extract_title_none_without_h1() -> None:
    assert _extract_title("h2는 아님\n## Section") is None


# ── _slugify ──────────────────────────────────────────────────────────────────

def test_slugify_basic() -> None:
    assert _slugify("Hello World") == "hello-world"


def test_slugify_collapses_spaces() -> None:
    assert _slugify("foo  bar") == "foo-bar"


def test_slugify_removes_special_chars() -> None:
    assert _slugify("what!? is this.") == "what-is-this"


def test_slugify_korean() -> None:
    assert _slugify("삽질 기록") == "삽질-기록"


def test_slugify_empty_falls_back_to_draft() -> None:
    assert _slugify("!@#$") == "draft"


# ── run() — happy path ────────────────────────────────────────────────────────

async def test_run_returns_path_and_title(tmp_path: Path) -> None:
    workflow, _ = _make_workflow(tmp_path)
    test_bus = EventBus()

    with patch("hub.workflows.draft_post.bus", test_bus):
        result = await workflow.run("삽질 기록", "노트 내용")

    assert result["title"] == "삽질 기록"
    assert result["path"].endswith(".md")


async def test_run_creates_file_with_draft_content(tmp_path: Path) -> None:
    workflow, _ = _make_workflow(tmp_path)
    test_bus = EventBus()

    with patch("hub.workflows.draft_post.bus", test_bus):
        result = await workflow.run("삽질 기록", "노트")

    assert Path(result["path"]).read_text(encoding="utf-8") == _DRAFT_TEXT


async def test_run_filename_contains_today(tmp_path: Path) -> None:
    workflow, _ = _make_workflow(tmp_path)
    test_bus = EventBus()
    today = datetime.date.today().isoformat()

    with patch("hub.workflows.draft_post.bus", test_bus):
        result = await workflow.run("hello world", "notes")

    assert today in result["path"]
    assert "hello-world" in result["path"]


async def test_run_uses_topic_as_title_when_no_h1(tmp_path: Path) -> None:
    workflow, claude = _make_workflow(tmp_path)
    claude.generate_blog_draft.return_value = "본문만 있고 제목 없음"
    test_bus = EventBus()

    with patch("hub.workflows.draft_post.bus", test_bus):
        result = await workflow.run("My Topic", "notes")

    assert result["title"] == "My Topic"


# ── run() — service calls ─────────────────────────────────────────────────────

async def test_run_calls_claude_with_topic_and_notes(tmp_path: Path) -> None:
    workflow, claude = _make_workflow(tmp_path)
    test_bus = EventBus()

    with patch("hub.workflows.draft_post.bus", test_bus):
        await workflow.run("주제", "노트 내용")

    claude.generate_blog_draft.assert_awaited_once_with("주제", "노트 내용")


# ── run() — event publishing ──────────────────────────────────────────────────

async def test_run_publishes_draft_created_event(tmp_path: Path) -> None:
    workflow, _ = _make_workflow(tmp_path)
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("draft.created", capture)

    with patch("hub.workflows.draft_post.bus", test_bus):
        result = await workflow.run("삽질 기록", "노트")

    assert len(captured) == 1
    event, payload = captured[0]
    assert event == "draft.created"
    assert payload["path"] == result["path"]
    assert payload["title"] == result["title"]


# ── run() — error cases ───────────────────────────────────────────────────────

async def test_run_propagates_claude_error(tmp_path: Path) -> None:
    workflow, claude = _make_workflow(tmp_path)
    claude.generate_blog_draft.side_effect = RuntimeError("API error")

    with pytest.raises(RuntimeError, match="API error"):
        await workflow.run("주제", "노트")


async def test_run_creates_output_dir_if_missing(tmp_path: Path) -> None:
    output_dir = tmp_path / "new" / "nested" / "drafts"
    claude = AsyncMock()
    claude.generate_blog_draft.return_value = _DRAFT_TEXT
    workflow = DraftPostWorkflow(claude=claude, output_dir=output_dir)
    test_bus = EventBus()

    with patch("hub.workflows.draft_post.bus", test_bus):
        await workflow.run("주제", "노트")

    assert output_dir.exists()
