"""Kafka-based RealtimeBrokerPort implementation.

Refactored to reuse the shared messaging factory under
`infrastructure.external.messaging` with a single topic approach:
  - Topic: `rt_room_v1`
  - Envelope: application Envelope is serialized as JSON payload
  - Consumer group: unique per instance to ensure fan-out (broadcast)
"""
from __future__ import annotations

import asyncio
import threading
import os
import socket
from uuid import uuid4
from typing import Optional

from application.ports.realtime import Envelope, RealtimeBrokerPort, Handler
from core.logging_config import get_logger
from core.config import settings
from infrastructure.external.messaging import (
    create_consumer,
    create_publisher,
    Envelope as MsgEnvelope,
    HandleResult,
)
from infrastructure.external.messaging.config_builder import messaging_config_from_settings
from infrastructure.external.messaging.serializers import JsonSerializer


logger = get_logger(__name__)


def _unique_group_id() -> str:
    base = settings.kafka.client_id or "app"
    host = socket.gethostname()
    pid = os.getpid()
    rnd = uuid4().hex[:6]
    return f"{base}.rt.{host}.{pid}.{rnd}"


class KafkaRealtimeBroker(RealtimeBrokerPort):
    TOPIC = "rt_room_v1"

    def __init__(self) -> None:
        self._cfg = messaging_config_from_settings(settings.kafka)
        self._serializer = JsonSerializer()
        self._publisher = create_publisher(self._cfg, self._serializer)
        self._consumer = create_consumer(self._cfg, self._serializer)
        self._handler: Optional[Handler] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._consumer_thread: Optional[threading.Thread] = None

    async def publish(self, room: str, envelope: Envelope) -> None:  # type: ignore[override]
        # attach room in envelope (already in Envelope.room)
        data = envelope.model_dump(mode="json")
        msg = MsgEnvelope(payload=data)
        # Publisher is sync; offload to thread to avoid blocking the loop
        await asyncio.to_thread(self._publisher.publish, self.TOPIC, msg)

    async def subscribe(self, handler: Handler) -> None:  # type: ignore[override]
        self._handler = handler
        self._loop = asyncio.get_running_loop()
        group_id = _unique_group_id()
        self._consumer.subscribe([self.TOPIC], group_id)

        def _on_message(msg_env: MsgEnvelope):
            try:
                payload = msg_env.payload
                if not isinstance(payload, dict):
                    return HandleResult.ACK
                env = Envelope.model_validate(payload)
            except Exception as exc:
                logger.warning("kafka_rt_parse_failed", error=str(exc))
                return HandleResult.ACK
            try:
                assert self._loop is not None and self._handler is not None
                asyncio.run_coroutine_threadsafe(self._handler(env), self._loop)
            except Exception as exc:
                logger.warning("kafka_rt_schedule_failed", error=str(exc))
            return HandleResult.ACK

        def _run_consumer():
            try:
                self._consumer.start(_on_message)
            except Exception as exc:
                logger.error("kafka_consumer_start_failed", error=str(exc))

        # Run in background thread (works for both confluent and aiokafka providers)
        t = threading.Thread(target=_run_consumer, name="kafka-rt-consumer", daemon=True)
        t.start()
        self._consumer_thread = t

    async def aclose(self) -> None:  # type: ignore[override]
        try:
            self._consumer.stop()
        except Exception:
            pass
        if self._consumer_thread is not None:
            try:
                self._consumer_thread.join(timeout=2)
            except Exception:
                pass
            self._consumer_thread = None
        try:
            self._publisher.close()
        except Exception:
            pass

