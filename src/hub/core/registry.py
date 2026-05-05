from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from hub.adapters.base import Adapter

logger = structlog.get_logger(__name__)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        self._adapters[adapter.name] = adapter
        logger.debug("registry.registered", adapter=adapter.name)

    def get(self, name: str) -> Adapter | None:
        return self._adapters.get(name)

    def all(self) -> list[Adapter]:
        return list(self._adapters.values())

    async def start_all(self) -> None:
        for adapter in self._adapters.values():
            logger.info("registry.starting", adapter=adapter.name)
            await adapter.start()

    async def stop_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                logger.info("registry.stopping", adapter=adapter.name)
                await adapter.stop()
            except Exception as exc:
                logger.warning("registry.stop_error", adapter=adapter.name, error=str(exc))

    async def healthcheck_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, adapter in self._adapters.items():
            try:
                results[name] = await adapter.healthcheck()
            except Exception as exc:
                logger.warning("registry.healthcheck_error", adapter=name, error=str(exc))
                results[name] = False
        return results


registry = AdapterRegistry()
