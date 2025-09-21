"""
Realtime port and message DTOs (contracts-first).

This module defines the boundary DTOs and the RealtimeBrokerPort
protocol so the application layer can remain decoupled from the
concrete messaging/broadcast implementations (infrastructure).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def _utc_now_z() -> str:
    ts = datetime.now(timezone.utc)
    s = ts.isoformat()
    return s.replace("+00:00", "Z")


class Envelope(BaseModel):
    """Unified WS message envelope passed around the system.

    Fields:
      - type: semantic message type (join/leave/message/ping/pong/system/error)
      - room: optional room channel
      - data: payload (JSON-serializable)
      - ts: server-generated UTC timestamp (ISO8601 with Z)
      - sender_id: optional user id set by server
    """

    type: str
    room: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=_utc_now_z)
    sender_id: int | None = None


Handler = Callable[[Envelope], Awaitable[None]]


class RealtimeBrokerPort(Protocol):
    """Abstraction for cross-process broadcast.

    Implementations may be in-memory (single process), Redis pub/sub,
    Kafka, etc. The application only depends on this contract.
    """

    async def publish(self, room: str, envelope: Envelope) -> None: ...

    async def subscribe(self, handler: Handler) -> None: ...

    # Optional but recommended; concrete implementations may provide it.
    async def aclose(self) -> None: ...  # pragma: no cover - optional


__all__ = ["Envelope", "RealtimeBrokerPort", "Handler"]

