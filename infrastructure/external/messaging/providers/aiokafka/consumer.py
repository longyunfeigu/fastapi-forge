from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ...base import ConsumeMiddleware, Consumer, Envelope, HandleResult, Serializer
from ...config import KafkaConfig, RetryConfig
from ...exceptions import NonRetryableError, RetryableError
from ...middlewares.retry import RetryPolicy
from ...envelope import (
    H_ERROR_CLASS,
    H_ERROR_MSG,
    H_RETRY_NOT_BEFORE,
    bump_attempts,
    ensure_original_topic,
    now_ms,
    set_not_before_ms,
)
from ._loop import LoopThread


def _from_headers(raw: Optional[List[tuple[str, bytes]]]) -> Dict[str, bytes]:
    headers: Dict[str, bytes] = {}
    if not raw:
        return headers
    for k, v in raw:
        headers[k] = v
    return headers


class AiokafkaConsumer(Consumer):
    def __init__(
        self,
        cfg: KafkaConfig,
        retry: RetryConfig,
        serializer: Serializer,
        middlewares: Optional[List[ConsumeMiddleware]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.cfg = cfg
        self.retry_cfg = retry
        self.serializer = serializer
        self.middlewares = middlewares or []
        self.log = logger or logging.getLogger("messaging.aiokafka.consumer")
        self._group_id: Optional[str] = None
        self._topics: Optional[List[str]] = None
        self._stopped = False
        self._retry_policy = RetryPolicy(retry)
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "aiokafka is required for AiokafkaConsumer. Install via `pip install aiokafka`."
            ) from e
        self._AIOKafkaConsumer = AIOKafkaConsumer
        self._AIOKafkaProducer = AIOKafkaProducer
        self._loop = LoopThread()
        self._consumer = None
        self._producer = None

    def subscribe(self, topics: List[str], group_id: str) -> None:
        self._topics = topics
        self._group_id = group_id

    def start(self, handler: Consumer.Handler) -> None:
        if not self._topics or not self._group_id:
            raise RuntimeError("Call subscribe(topics, group_id) before start().")

        self._loop.start()

        async def _run():
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

            self._consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=self.cfg.bootstrap_servers,
                group_id=self._group_id,
                enable_auto_commit=False,
                auto_offset_reset=self.cfg.consumer.auto_offset_reset,
            )
            await self._consumer.start()
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.cfg.bootstrap_servers,
                client_id=self.cfg.client_id + ".consumer-producer",
                compression_type=self.cfg.producer.compression_type,
            )
            await self._producer.start()

            try:
                while not self._stopped:
                    msg = await self._consumer.getone()
                    topic = msg.topic
                    partition = msg.partition
                    offset = msg.offset
                    headers = _from_headers(msg.headers)
                    value = msg.value
                    key = msg.key

                    not_before = headers.get(H_RETRY_NOT_BEFORE)
                    if not_before is not None:
                        try:
                            ts = int(not_before.decode("ascii"))
                        except Exception:
                            ts = None  # type: ignore
                        if ts is not None and ts > now_ms():
                            # pause and seek this partition until ts
                            tp = msg.topic, msg.partition
                            self._consumer.pause(tp)
                            # aiokafka seek takes TopicPartition-like tuple
                            await self._consumer.seek(tp, msg.offset)
                            # naive sleep until due
                            delay = max(0, (ts - now_ms()) / 1000.0)
                            await asyncio.sleep(delay)
                            self._consumer.resume(tp)
                            continue

                    try:
                        payload = self.serializer.loads(value) if value is not None else None
                    except Exception as e:  # noqa: BLE001
                        dlq = f"{topic}.{self.retry_cfg.dlq_suffix}"
                        headers[H_ERROR_CLASS] = b"SerializationError"
                        headers[H_ERROR_MSG] = str(e).encode("utf-8")[:2048]
                        await self._producer.send_and_wait(dlq, value=value, key=key, headers=msg.headers)
                        await self._consumer.commit()
                        continue

                    env = Envelope(payload=payload, key=key, headers=headers)
                    for m in self.middlewares:
                        env = m.before_handle(topic, partition, offset, env)

                    result = HandleResult.ACK
                    err: Optional[BaseException] = None
                    try:
                        result = handler(env)
                    except RetryableError as e:
                        result = HandleResult.RETRY
                        err = e
                    except NonRetryableError as e:
                        result = HandleResult.DROP
                        err = e
                    except Exception as e:  # noqa: BLE001
                        result = HandleResult.RETRY
                        err = e

                    try:
                        if result == HandleResult.ACK:
                            await self._consumer.commit()
                        elif result == HandleResult.RETRY:
                            decision = self._retry_policy.next_for_retry(topic)
                            ensure_original_topic(headers, topic)
                            bump_attempts(headers)
                            if not decision.is_dlq:
                                set_not_before_ms(headers, now_ms() + decision.delay_ms)
                            if err is not None:
                                headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
                                headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
                            await self._producer.send_and_wait(decision.next_topic, value=value, key=key, headers=msg.headers)
                            await self._consumer.commit()
                        elif result == HandleResult.DROP:
                            dlq = f"{topic}.{self.retry_cfg.dlq_suffix}"
                            if err is not None:
                                headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
                                headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
                            await self._producer.send_and_wait(dlq, value=value, key=key, headers=msg.headers)
                            await self._consumer.commit()
                    finally:
                        for m in self.middlewares:
                            m.after_handle(topic, partition, offset, env, result, err)

            finally:
                try:
                    await self._consumer.stop()
                except Exception:
                    pass
                try:
                    await self._producer.stop()
                except Exception:
                    pass

        # import asyncio here to avoid top-level dep if unused
        import asyncio

        self._loop.run_coro(_run())

    def stop(self) -> None:
        self._stopped = True
        self._loop.stop()

