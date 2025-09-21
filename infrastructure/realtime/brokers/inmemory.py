"""In-memory implementation of RealtimeBrokerPort.

Single-process only. Useful for local dev and tests.
"""
from __future__ import annotations

from typing import List
import asyncio

from application.ports.realtime import Envelope, RealtimeBrokerPort, Handler


class InMemoryRealtimeBroker(RealtimeBrokerPort):
    def __init__(self) -> None:
        self._handlers: List[Handler] = []
        self._lock = asyncio.Lock()

    async def publish(self, room: str, envelope: Envelope) -> None:  # type: ignore[override]
        # Best-effort deliver sequentially
        async with self._lock:
            handlers = list(self._handlers)
        for h in handlers:
            await h(envelope)

    async def subscribe(self, handler: Handler) -> None:  # type: ignore[override]
        async with self._lock:
            self._handlers.append(handler)

    async def aclose(self) -> None:  # type: ignore[override]
        async with self._lock:
            self._handlers.clear()

