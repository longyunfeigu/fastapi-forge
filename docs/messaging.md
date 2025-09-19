Messaging Integration (Kafka)

Overview
- Unified API for publishing/consuming messages with middlewares (logging/metrics/tracing) and retry/DLQ strategy.
- Providers: confluent-kafka (default), aiokafka (async). Semantics: at-least-once.
- Delayed retry via pause/resume using header x-retry-not-before across layered retry topics: retry.5s → retry.1m → retry.10m → dlq.

Best Practices (Prod)
- Producer
  - Prefer batching: use publish_many() where possible; a single flush at the end.
  - Backpressure-aware produce with deadlines: queue-full (BufferError) retries for KAFKA__PRODUCER_SEND_WAIT_S.
  - Wait only for current record delivery (not global flush) with KAFKA__PRODUCER_DELIVERY_WAIT_S timeout.
  - Tuning keys: KAFKA__PRODUCER_LINGER_MS, KAFKA__PRODUCER_BATCH_SIZE, KAFKA__PRODUCER_MESSAGE_TIMEOUT_MS, KAFKA__PRODUCER_MAX_IN_FLIGHT.
- Consumer
  - Non-transactional path: on RETRY/DROP requeue then sync-commit that partition's offset to avoid duplicates; commit-by-count/time remains for ACK.
  - Rebalance safety: on_revoke commits last processed offsets; on_assign clears paused partitions.
  - Transactional path: when transactional.id is set, requeue/DLQ and offset commit are done atomically per transaction.
  - Consider isolation.level=read_committed for consumers that must not see uncommitted transactional records.

Install
- Add dependencies (already included in requirements.txt):
  - confluent-kafka>=2.3,<3
  - aiokafka>=0.10,<1 (only if using async adapter)
- Optional: prometheus_client, opentelemetry-api for metrics/tracing middlewares.

Configure
- Environment overrides (examples, nested with __):
  - KAFKA__BOOTSTRAP_SERVERS=localhost:9092
  - KAFKA__CLIENT_ID=order-svc
  - KAFKA__DRIVER=confluent (or aiokafka)
- Topic naming: <biz>.<event>.v<n>
- Retry topics: <main>.retry.5s, <main>.retry.1m, <main>.retry.10m
- DLQ: <main>.dlq

Code Usage
from infrastructure.external.messaging import HandleResult
from infrastructure.external.messaging.serializers.json import JsonSerializer
from infrastructure.external.messaging.middlewares import LoggingMiddleware, MetricsMiddleware
from infrastructure.external.messaging.factory import create_publisher, create_consumer
from infrastructure.external.messaging.config_builder import messaging_config_from_settings
from core.config import settings

# Producer
cfg = messaging_config_from_settings(settings.kafka)
pub = create_publisher(cfg, JsonSerializer(), [LoggingMiddleware(), MetricsMiddleware()])
pub.publish("order.created.v1", env=type("Env", (), {})())  # see example script for Envelope usage
pub.close()

# Consumer
con = create_consumer(cfg, JsonSerializer(), [LoggingMiddleware(), MetricsMiddleware()])
con.subscribe(["order.created.v1","order.created.v1.retry.5s","order.created.v1.retry.1m","order.created.v1.retry.10m"], group_id="order-svc")
def handler(env):
  return HandleResult.ACK  # or raise RetryableError/NonRetryableError
con.start(handler)

Readiness & Shutdown
- The example script performs a basic readiness probe:
  - confluent driver: Consumer.list_topics(timeout=5)
  - aiokafka driver: start/stop AIOKafkaProducer
- Graceful shutdown: on SIGINT/SIGTERM, consumer.stop() flushes and closes.

Run the Demo
1) Ensure Kafka is reachable at KAFKA__BOOTSTRAP_SERVERS.
2) Producer: python examples/messaging_demo.py produce --topic demo.topic.v1 --count 5 --interval 0.2
3) Consumer (separate terminal): python examples/messaging_demo.py consume --topic demo.topic.v1 --group demo-group

Notes
- For metrics/tracing, install optional deps and configure exporters as needed.
- Retry/DLQ routing occurs in consumer path. On RETRY/DROP, the consumer publishes to next retry topic or DLQ, then commits the current offset.
- For strict ordering per key, set envelope.key to a stable business key.
