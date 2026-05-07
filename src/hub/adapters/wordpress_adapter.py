from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from hub.adapters.base import Adapter
from hub.core.config import get_settings

logger = structlog.get_logger(__name__)


class WordPressAdapter(Adapter):
    def __init__(self) -> None:
        cfg = get_settings().wordpress
        self._url = cfg.url.rstrip("/")
        self._username = cfg.username
        self._password = cfg.password
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "wordpress"

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            auth=(self._username, self._password),
            timeout=30.0,
        )
        logger.info("wordpress.started", url=self._url)

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("wordpress.stopped")

    async def healthcheck(self) -> bool:
        if self._client is None:
            return False
        try:
            resp = await self._client.get(f"{self._url}/wp-json/wp/v2/")
            return resp.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def create_post(
        self,
        *,
        title: str,
        content: str,
        status: str = "publish",
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("WordPressAdapter not started")
        resp = await self._client.post(
            f"{self._url}/wp-json/wp/v2/posts",
            json={"title": title, "content": content, "status": status},
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        logger.info("wordpress.post_created", post_id=data["id"], status=status)
        return {"id": data["id"], "url": data["link"]}
