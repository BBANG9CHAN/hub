from __future__ import annotations

from abc import ABC, abstractmethod


class Adapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def healthcheck(self) -> bool: ...
