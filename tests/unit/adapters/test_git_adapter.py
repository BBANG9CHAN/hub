from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hub.adapters.git_adapter import GitAdapter
from hub.core.bus import EventBus


async def _to_thread_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
    """asyncio.to_thread 대신 동기 실행 — 테스트용."""
    return func(*args, **kwargs)


@pytest.fixture
def mock_repo() -> MagicMock:
    commit = MagicMock()
    commit.hexsha = "abc123def456abc1"
    repo = MagicMock()
    repo.bare = False
    repo.index.commit.return_value = commit
    return repo


def _start_patches(mock_repo: MagicMock, test_bus: EventBus) -> tuple[Any, Any, Any]:
    p_repo = patch("hub.adapters.git_adapter.Repo", return_value=mock_repo)
    p_thread = patch("asyncio.to_thread", new=_to_thread_sync)
    p_bus = patch("hub.adapters.git_adapter.bus", test_bus)
    return p_repo, p_thread, p_bus


async def test_name() -> None:
    adapter = GitAdapter(repo_path="/tmp/test")
    assert adapter.name == "git"


async def test_start_initialises_repo(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
    assert adapter._repo is mock_repo


async def test_start_subscribes_post_published(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
    assert len(test_bus._subscribers["post.published"]) == 1


async def test_stop_clears_repo_and_unsubscribes(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
        await adapter.stop()
    assert adapter._repo is None
    assert len(test_bus._subscribers["post.published"]) == 0


async def test_healthcheck_true_when_started(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
        result = await adapter.healthcheck()
    assert result is True


async def test_healthcheck_false_when_not_started() -> None:
    adapter = GitAdapter(repo_path="/tmp/blog")
    assert await adapter.healthcheck() is False


async def test_commit_and_push_calls_git_ops(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
        await adapter.commit_and_push("posts/foo.md", "publish: foo")

    mock_repo.index.add.assert_called_once_with(["posts/foo.md"])
    mock_repo.index.commit.assert_called_once_with("publish: foo")
    mock_repo.remote("origin").push.assert_called()


async def test_commit_and_push_publishes_events(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    captured: list[tuple[str, Any]] = []

    async def capture(event: str, payload: Any) -> None:
        captured.append((event, payload))

    test_bus.subscribe("git.committed", capture)
    test_bus.subscribe("git.pushed", capture)

    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
        await adapter.commit_and_push("posts/foo.md", "publish: foo")

    events = [e for e, _ in captured]
    assert "git.committed" in events
    assert "git.pushed" in events


async def test_commit_and_push_raises_when_not_started() -> None:
    adapter = GitAdapter(repo_path="/tmp/blog")
    with pytest.raises(RuntimeError, match="not started"):
        await adapter.commit_and_push("foo.md", "msg")


async def test_on_post_published_triggers_commit(mock_repo: MagicMock) -> None:
    test_bus = EventBus()
    p_repo, p_thread, p_bus = _start_patches(mock_repo, test_bus)
    with p_repo, p_thread, p_bus:
        adapter = GitAdapter(repo_path="/tmp/blog")
        await adapter.start()
        await adapter._on_post_published(
            "post.published",
            {"filepath": "posts/x.md", "commit_message": "publish: x"},
        )

    mock_repo.index.add.assert_called_once_with(["posts/x.md"])
    mock_repo.index.commit.assert_called_once_with("publish: x")
