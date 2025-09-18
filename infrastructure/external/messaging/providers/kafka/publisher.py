from __future__ import annotations

from typing import List, Optional

from ...base import Envelope, PublishMiddleware, PublishResult, Publisher, Serializer
from ...config import KafkaConfig
from ...exceptions import PublishError


def _to_confluent_headers(headers: dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


class KafkaPublisher(Publisher):
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
            from confluent_kafka import Producer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "confluent_kafka is required for KafkaPublisher. Install via `pip install confluent-kafka`."
            ) from e

        conf: dict = {
            "bootstrap.servers": cfg.bootstrap_servers,
            "client.id": cfg.client_id,
            "enable.idempotence": cfg.producer.enable_idempotence,
            "compression.type": cfg.producer.compression_type,
            "linger.ms": cfg.producer.linger_ms,
            "acks": cfg.producer.acks,
            "message.send.max.retries": 10,
            "max.in.flight.requests.per.connection": cfg.producer.max_in_flight,
        }
        if cfg.tls.enable:
            conf.update({
                "security.protocol": "SSL" if not cfg.sasl.mechanism else "SASL_SSL",
                "ssl.ca.location": cfg.tls.ca_location,
                "ssl.certificate.location": cfg.tls.certificate,
                "ssl.key.location": cfg.tls.key,
                "enable.ssl.certificate.verification": cfg.tls.verify,
            })
        if cfg.sasl.mechanism:
            conf.update({
                "sasl.mechanism": cfg.sasl.mechanism,
                "sasl.username": cfg.sasl.username,
                "sasl.password": cfg.sasl.password,
            })
        self._Producer = Producer
        self._producer = Producer(conf)

    def publish(self, topic: str, env: Envelope) -> PublishResult:
        # middlewares before
        for m in self.middlewares:
            env = m.before_publish(topic, env)

        value_bytes = env.payload if isinstance(env.payload, (bytes, bytearray)) else self.serializer.dumps(env.payload)
        key = env.key

        meta_holder: dict = {}

        def _delivery(err, msg):  # type: ignore[no-redef]
            if err is not None:
                meta_holder["error"] = err
            else:
                meta_holder["result"] = PublishResult(
                    topic=msg.topic(), partition=msg.partition(), offset=msg.offset(), timestamp=msg.timestamp()[1]
                )

        try:
            self._producer.produce(
                topic=topic,
                key=key,
                value=bytes(value_bytes),
                headers=_to_confluent_headers(env.headers),
                on_delivery=_delivery,
            )
        except BufferError as e:
            # backpressure: block until queue drains
            self._producer.poll(0.1)
            raise PublishError(str(e)) from e

        self._producer.flush()

        if "error" in meta_holder:
            raise PublishError(str(meta_holder["error"]))
        result = meta_holder.get("result")
        if not result:
            raise PublishError("No delivery report")

        for m in self.middlewares:
            m.after_publish(topic, env, result)
        return result

    def close(self) -> None:
        try:
            self._producer.flush(5)
        except Exception:
            pass

