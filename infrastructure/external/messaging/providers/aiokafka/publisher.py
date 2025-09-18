from __future__ import annotations

from typing import List, Optional

from ...base import Envelope, PublishMiddleware, PublishResult, Publisher, Serializer
from ...config import KafkaConfig
from ._loop import LoopThread


def _to_headers(headers: dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


class AiokafkaPublisher(Publisher):
    def __init__(
        self,
        cfg: KafkaConfig,
        serializer: Serializer,
        middlewares: Optional[List[PublishMiddleware]] = None,
    ) -> None:
        self.cfg = cfg
        self.serializer = serializer
        self.middlewares = middlewares or []
        try:
            from aiokafka import AIOKafkaProducer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "aiokafka is required for AiokafkaPublisher. Install via `pip install aiokafka`."
            ) from e
        self._AIOKafkaProducer = AIOKafkaProducer
        self._loop = LoopThread()
        self._loop.start()
        self._producer = self._loop.run_coro(
            self._create_producer()
        )

    async def _create_producer(self):
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(
            bootstrap_servers=self.cfg.bootstrap_servers,
            client_id=self.cfg.client_id,
            compression_type=self.cfg.producer.compression_type,
        )
        await producer.start()
        return producer

    def publish(self, topic: str, env: Envelope) -> PublishResult:
        for m in self.middlewares:
            env = m.before_publish(topic, env)
        value_bytes = env.payload if isinstance(env.payload, (bytes, bytearray)) else self.serializer.dumps(env.payload)
        key = env.key

        async def _send():
            md = await self._producer.send_and_wait(
                topic, value=value_bytes, key=key, headers=_to_headers(env.headers)
            )
            return md

        md = self._loop.run_coro(_send())
        result = PublishResult(topic=topic, partition=md.partition, offset=md.offset, timestamp=None)
        for m in self.middlewares:
            m.after_publish(topic, env, result)
        return result

    def close(self) -> None:
        async def _stop():
            await self._producer.stop()

        try:
            self._loop.run_coro(_stop())
        finally:
            self._loop.stop()

