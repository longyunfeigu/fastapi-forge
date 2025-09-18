Messaging Integration (Kafka)

Overview
- Unified API for publishing/consuming messages with middlewares (logging/metrics/tracing) and retry/DLQ strategy.
- Providers: confluent-kafka (default), aiokafka (async). Semantics: at-least-once.
- Delayed retry via pause/resume using header x-retry-not-before across layered retry topics: retry.5s → retry.1m → retry.10m → dlq.

Install
- Add dependencies (already included in requirements.txt):
  - confluent-kafka>=2.3,<3
  - aiokafka>=0.10,<1 (only if using async adapter)
- Optional: prometheus_client, opentelemetry-api for metrics/tracing middlewares.

Configure
- Environment overrides (examples):
  - KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  - KAFKA_CLIENT_ID=order-svc
  - KAFKA_DRIVER=confluent (or aiokafka)
- Topic naming: <biz>.<event>.v<n>
- Retry topics: <main>.retry.5s, <main>.retry.1m, <main>.retry.10m
- DLQ: <main>.dlq

Code Usage
from infrastructure.external.messaging import MessagingConfig, HandleResult
from infrastructure.external.messaging.serializers.json import JsonSerializer
from infrastructure.external.messaging.middlewares import LoggingMiddleware, MetricsMiddleware
from infrastructure.external.messaging.factory import create_publisher, create_consumer

# Producer
cfg = MessagingConfig()
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
1) Ensure Kafka is reachable at KAFKA_BOOTSTRAP_SERVERS.
2) Producer: python examples/messaging_demo.py produce --topic demo.topic.v1 --count 5 --interval 0.2
3) Consumer (separate terminal): python examples/messaging_demo.py consume --topic demo.topic.v1 --group demo-group

Notes
- For metrics/tracing, install optional deps and configure exporters as needed.
- Retry/DLQ routing occurs in consumer path. On RETRY/DROP, the consumer publishes to next retry topic or DLQ, then commits the current offset.
- For strict ordering per key, set envelope.key to a stable business key.

