from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone

from infrastructure.external.messaging import (
    MessagingConfig,
    HandleResult,
)
from infrastructure.external.messaging.serializers.json import JsonSerializer
from infrastructure.external.messaging.base import Envelope
from infrastructure.external.messaging.middlewares import LoggingMiddleware, MetricsMiddleware
from infrastructure.external.messaging.factory import create_publisher, create_consumer


def _apply_env(cfg: MessagingConfig) -> None:
    bs = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if bs:
        cfg.kafka.bootstrap_servers = bs
    driver = os.getenv("KAFKA_DRIVER")
    if driver in {"confluent", "aiokafka"}:
        cfg.kafka.driver = driver  # type: ignore
    client_id = os.getenv("KAFKA_CLIENT_ID")
    if client_id:
        cfg.kafka.client_id = client_id


def check_readiness(cfg: MessagingConfig, timeout: float = 5.0) -> bool:
    if cfg.kafka.driver == "confluent":
        try:
            from confluent_kafka import Consumer

            c = Consumer(
                {
                    "bootstrap.servers": cfg.kafka.bootstrap_servers,
                    "group.id": cfg.kafka.client_id + ".health",
                    "enable.auto.commit": False,
                }
            )
            md = c.list_topics(timeout=timeout)
            c.close()
            return md is not None
        except Exception as e:  # noqa: BLE001
            print(f"[readiness] confluent check failed: {e}")
            return False
    else:
        try:
            import asyncio
            from aiokafka import AIOKafkaProducer

            async def _probe():
                p = AIOKafkaProducer(bootstrap_servers=cfg.kafka.bootstrap_servers)
                await p.start()
                await p.stop()
                return True

            return asyncio.run(_probe())
        except Exception as e:  # noqa: BLE001
            print(f"[readiness] aiokafka check failed: {e}")
            return False


def run_producer(topic: str, key: bytes | None, count: int, interval: float) -> None:
    cfg = MessagingConfig()
    _apply_env(cfg)
    if not check_readiness(cfg):
        print("Broker not ready; aborting.")
        sys.exit(2)
    pub = create_publisher(cfg, JsonSerializer(), [LoggingMiddleware(), MetricsMiddleware()])
    try:
        for i in range(count):
            payload = {
                "i": i,
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "hello": "world",
            }
            env = Envelope(payload=payload, key=key, headers={})
            res = pub.publish(topic, env)
            print(f"published -> {res.topic}[{res.partition}]@{res.offset}")
            if interval > 0:
                time.sleep(interval)
    finally:
        pub.close()


def run_consumer(topic: str, group: str) -> None:
    cfg = MessagingConfig()
    _apply_env(cfg)
    if not check_readiness(cfg):
        print("Broker not ready; aborting.")
        sys.exit(2)
    con = create_consumer(cfg, JsonSerializer(), [LoggingMiddleware(), MetricsMiddleware()])
    topics = [
        topic,
        f"{topic}.retry.5s",
        f"{topic}.retry.1m",
        f"{topic}.retry.10m",
    ]
    con.subscribe(topics, group_id=group)

    stop_flag = {"stop": False}

    def _sig(*_):
        stop_flag["stop"] = True
        con.stop()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    def handler(env):
        # Print and ack by default
        print("consumed:", json.dumps(env.payload, ensure_ascii=False))
        return HandleResult.ACK

    con.start(handler)


def main() -> None:
    ap = argparse.ArgumentParser(description="Messaging demo (Kafka)")
    ap.add_argument("mode", choices=["produce", "consume"], help="Run as producer or consumer")
    ap.add_argument("--topic", default="demo.topic.v1")
    ap.add_argument("--group", default="demo-group")
    ap.add_argument("--key", default=None)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--interval", type=float, default=0.0)
    args = ap.parse_args()

    key = args.key.encode("utf-8") if args.key else None
    if args.mode == "produce":
        run_producer(args.topic, key, args.count, args.interval)
    else:
        run_consumer(args.topic, args.group)


if __name__ == "__main__":
    main()
