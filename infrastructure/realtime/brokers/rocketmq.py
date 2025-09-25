"""RocketMQ-based RealtimeBrokerPort implementation.

Uses Apache RocketMQ Python client (`rocketmq` package, PushConsumer/Producer).

Design:
- Single topic `rt_room_v1` to carry all room events; envelope contains room
  so we can route to in-process connections.

Notes:
- The official `rocketmq` client is synchronous and drives callbacks from
  background threads; we schedule the async handler onto the main event loop.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional, Any

from application.ports.realtime import Envelope, RealtimeBrokerPort, Handler
from core.config import settings
from core.logging_config import get_logger


logger = get_logger(__name__)


class RocketMQRealtimeBroker(RealtimeBrokerPort):
    def __init__(self) -> None:
        # Imports are optional; raise helpful error if missing at runtime
        try:  # lazy import to avoid hard dependency
            from rocketmq.client import Producer, PushConsumer, Message, ConsumeStatus  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "rocketmq client library not installed. Please `pip install rocketmq` (Apache RocketMQ)."
            ) from exc

        # Cache references to types (avoid re-import in methods)
        self._Producer = Producer  # type: ignore
        self._PushConsumer = PushConsumer  # type: ignore
        self._Message = Message  # type: ignore
        self._ConsumeStatus = ConsumeStatus  # type: ignore

        self._handler: Optional[Handler] = None
        self._producer: Optional[Any] = None
        self._consumer: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stopping = asyncio.Event()

        # Config
        self._endpoints = settings.rocketmq.endpoints
        self._topic = settings.rocketmq.topic or "rt_room_v1"
        self._producer_group = settings.rocketmq.producer_group or "rt-realtime-producer"
        self._consumer_group = settings.rocketmq.consumer_group or "rt-realtime-consumer"
        self._access_key = settings.rocketmq.access_key
        self._secret_key = settings.rocketmq.secret_key

    # --------------------------- Common API ---------------------------
    async def publish(self, room: str, envelope: Envelope) -> None:  # type: ignore[override]
        if self._producer is None:
            self._ensure_producer()
        assert self._producer is not None
        body = json.dumps(envelope.model_dump(mode="json")).encode("utf-8")
        msg = self._Message(self._topic)
        # Use room as tag for optional server-side filtering
        tag = (room or "").replace(" ", "_")[:128] or "_"
        try:
            msg.set_tags(tag)
        except Exception:
            # Some clients may restrict tag charset; ignore if invalid
            pass
        msg.set_body(body)
        try:
            # Send sync; RocketMQ client is synchronous, this is fast for small payloads
            await asyncio.to_thread(self._producer.send_sync, msg)
        except Exception as exc:  # pragma: no cover
            logger.error("rocketmq_publish_failed", topic=self._topic, error=str(exc))

    async def subscribe(self, handler: Handler) -> None:  # type: ignore[override]
        self._handler = handler
        self._loop = asyncio.get_running_loop()
        self._ensure_consumer()
        assert self._consumer is not None

        def _on_message(msg):  # called in rocketmq thread
            try:
                data = msg.body
                env = Envelope.model_validate_json(data)
            except Exception as exc:
                logger.warning("rocketmq_parse_failed", error=str(exc))
                return self._ConsumeStatus.CONSUME_SUCCESS
            try:
                assert self._loop is not None and self._handler is not None
                # Schedule onto asyncio loop and ignore result
                asyncio.run_coroutine_threadsafe(self._handler(env), self._loop)
            except Exception as exc:
                logger.warning("rocketmq_handler_schedule_failed", error=str(exc))
            return self._ConsumeStatus.CONSUME_SUCCESS

        try:
            self._consumer.register_message_listener(_on_message)
            self._consumer.start()
            logger.info("rocketmq_consumer_started", topic=self._topic)
        except Exception as exc:  # pragma: no cover
            logger.error("rocketmq_consumer_start_failed", error=str(exc))

    async def aclose(self) -> None:  # type: ignore[override]
        self._stopping.set()
        if self._consumer is not None:
            try:
                self._consumer.shutdown()
            except Exception:
                pass
            self._consumer = None
        if self._producer is not None:
            try:
                self._producer.shutdown()
            except Exception:
                pass
            self._producer = None

    # --------------------------- Internals ----------------------------
    def _ensure_producer(self) -> None:
        if self._producer is not None:
            return
        p = self._Producer(self._producer_group)
        if self._endpoints:
            try:
                p.set_namesrv_addr(self._endpoints)
            except Exception:
                # Some client versions use set_name_server_address
                try:
                    p.set_name_server_address(self._endpoints)
                except Exception:
                    pass
        # Auth (if configured by provider)
        if self._access_key and self._secret_key:
            try:
                p.set_session_credentials(self._access_key, self._secret_key, "")
            except Exception:
                pass
        p.start()
        self._producer = p

    def _ensure_consumer(self) -> None:
        if self._consumer is not None:
            return
        c = self._PushConsumer(self._consumer_group)
        if self._endpoints:
            try:
                c.set_namesrv_addr(self._endpoints)
            except Exception:
                try:
                    c.set_name_server_address(self._endpoints)
                except Exception:
                    pass
        # Subscribe to all tags; room is available inside payload
        c.subscribe(self._topic, "*")
        if self._access_key and self._secret_key:
            try:
                c.set_session_credentials(self._access_key, self._secret_key, "")
            except Exception:
                pass
        self._consumer = c


