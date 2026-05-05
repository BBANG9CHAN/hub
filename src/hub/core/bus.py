from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

Handler = Callable[[str, Any], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._subscribers[event].append(handler)
        logger.debug("bus.subscribed", bus_event=event, handler=handler.__qualname__)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._subscribers.get(event, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    async def publish(self, event: str, payload: Any = None) -> None:
        handlers = list(self._subscribers.get(event, []))
        logger.info("bus.publish", bus_event=event, handler_count=len(handlers))
        if not handlers:
            return
        results = await asyncio.gather(
            *[h(event, payload) for h in handlers],
            return_exceptions=True,
        )
        for handler, result in zip(handlers, results):
            if isinstance(result, BaseException):
                logger.error(
                    "bus.handler_error",
                    bus_event=event,
                    handler=handler.__qualname__,
                    error=str(result),
                    exc_info=result,
                )


bus = EventBus()
