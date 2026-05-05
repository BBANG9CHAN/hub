from __future__ import annotations

import pytest
from hub.core.bus import EventBus


async def test_publish_calls_subscriber() -> None:
    bus = EventBus()
    received: list[tuple[str, object]] = []

    async def handler(event: str, payload: object) -> None:
        received.append((event, payload))

    bus.subscribe("test.event", handler)
    await bus.publish("test.event", {"key": "value"})

    assert received == [("test.event", {"key": "value"})]


async def test_publish_no_subscribers_does_not_raise() -> None:
    bus = EventBus()
    await bus.publish("test.event", None)


async def test_multiple_subscribers_all_called() -> None:
    bus = EventBus()
    calls: list[str] = []

    async def h1(event: str, payload: object) -> None:
        calls.append("h1")

    async def h2(event: str, payload: object) -> None:
        calls.append("h2")

    bus.subscribe("test.event", h1)
    bus.subscribe("test.event", h2)
    await bus.publish("test.event", None)

    assert sorted(calls) == ["h1", "h2"]


async def test_handler_exception_does_not_propagate() -> None:
    bus = EventBus()

    async def bad_handler(event: str, payload: object) -> None:
        raise RuntimeError("intentional error")

    async def good_handler(event: str, payload: object) -> None:
        pass

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)
    await bus.publish("test.event", None)  # should not raise


async def test_unsubscribe_removes_handler() -> None:
    bus = EventBus()
    calls: list[str] = []

    async def handler(event: str, payload: object) -> None:
        calls.append("called")

    bus.subscribe("test.event", handler)
    bus.unsubscribe("test.event", handler)
    await bus.publish("test.event", None)

    assert calls == []


async def test_different_events_are_isolated() -> None:
    bus = EventBus()
    received: list[str] = []

    async def handler(event: str, payload: object) -> None:
        received.append(event)

    bus.subscribe("a.event", handler)
    await bus.publish("b.event", None)

    assert received == []
