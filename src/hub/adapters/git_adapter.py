from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog
from git import InvalidGitRepositoryError, Repo
from tenacity import retry, stop_after_attempt, wait_fixed

from hub.adapters.base import Adapter
from hub.core.bus import bus
from hub.core.config import get_settings

logger = structlog.get_logger(__name__)


class GitAdapter(Adapter):
    def __init__(self, repo_path: str | None = None) -> None:
        cfg = get_settings().git
        self._repo_path = Path(repo_path or cfg.blog_repo_path)
        self._repo: Repo | None = None

    @property
    def name(self) -> str:
        return "git"

    async def start(self) -> None:
        try:
            self._repo = await asyncio.to_thread(Repo, self._repo_path)
        except InvalidGitRepositoryError as e:
            logger.error("git.start_failed", path=str(self._repo_path), error=str(e))
            raise
        bus.subscribe("post.published", self._on_post_published)
        logger.info("git.started", repo=str(self._repo_path))

    async def stop(self) -> None:
        bus.unsubscribe("post.published", self._on_post_published)
        self._repo = None
        logger.info("git.stopped")

    async def healthcheck(self) -> bool:
        if self._repo is None:
            return False
        try:
            return not self._repo.bare
        except Exception:
            return False

    async def commit_and_push(self, filepath: str, message: str) -> None:
        if self._repo is None:
            raise RuntimeError("GitAdapter not started")
        await self._push(filepath, message)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _push(self, filepath: str, message: str) -> None:
        repo = self._repo

        def _do_commit() -> str:
            repo.index.add([filepath])
            commit = repo.index.commit(message)
            return str(commit.hexsha)

        sha = await asyncio.to_thread(_do_commit)
        await bus.publish("git.committed", {"sha": sha, "message": message})
        logger.info("git.committed", sha=sha[:8], message=message)

        def _do_push() -> None:
            origin = repo.remote("origin")
            origin.push()

        await asyncio.to_thread(_do_push)
        await bus.publish("git.pushed", {"sha": sha, "remote": "origin"})
        logger.info("git.pushed", sha=sha[:8])

    async def _on_post_published(self, event: str, payload: Any) -> None:
        filepath = payload.get("filepath", "")
        message = payload.get("commit_message", f"publish: {filepath}")
        await self.commit_and_push(filepath, message)
