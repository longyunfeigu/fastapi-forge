"""
配置文件 - 项目配置管理
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from pydantic import model_validator


class GrpcTlsSettings(BaseModel):
    enabled: bool = False
    cert: Optional[str] = None
    key: Optional[str] = None
    ca: Optional[str] = None


class GrpcSettings(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 50051
    # This maps to GRPC option grpc.max_concurrent_streams
    max_concurrent_streams: int = 100
    tls: GrpcTlsSettings = Field(default_factory=GrpcTlsSettings)


class KafkaSettings(BaseModel):
    # Provider/driver
    provider: str = Field(default="kafka")
    driver: str = Field(default="confluent")  # confluent or aiokafka

    # Core Kafka
    bootstrap_servers: str = Field(default="localhost:9092")
    client_id: str = Field(default="app-messaging")
    transactional_id: Optional[str] = None

    # TLS
    tls_enable: bool = False
    tls_ca_location: Optional[str] = None
    tls_certificate: Optional[str] = None
    tls_key: Optional[str] = None
    tls_verify: bool = True

    # SASL
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None

    # Producer tuning
    producer_acks: str = "all"
    producer_enable_idempotence: bool = True
    producer_compression_type: str = "zstd"
    producer_linger_ms: int = 5
    producer_batch_size: int = 64 * 1024
    producer_max_in_flight: int = 5
    producer_message_timeout_ms: int = 120_000
    producer_send_wait_s: float = 5.0
    producer_delivery_wait_s: float = 30.0

    # Consumer tuning
    consumer_enable_auto_commit: bool = False
    consumer_auto_offset_reset: str = "latest"
    consumer_max_poll_interval_ms: int = 300000
    consumer_session_timeout_ms: int = 45000
    consumer_fetch_min_bytes: int = 1
    consumer_fetch_max_bytes: int = 50 * 1024 * 1024
    consumer_commit_every_n: int = 100
    consumer_commit_interval_ms: int = 2000
    consumer_max_concurrency: int = 1
    consumer_inflight_max: int = 1000

    # Retry policy
    retry_layers: Optional[str] = "retry.5s:5000,retry.1m:60000,retry.10m:600000"
    retry_dlq_suffix: str = "dlq"


class RedisSettings(BaseModel):
    url: Optional[str] = None
    max_connections: int = 10
    default_ttl: int = 300
    namespace: str = "fastapi-forge"


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://user:password@localhost/userdb"


class StorageSettings(BaseModel):
    type: str = "local"  # local, s3, oss
    bucket: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    public_base_url: Optional[str] = None
    # S3 specific
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_sse: Optional[str] = None
    s3_acl: str = "private"
    # OSS specific
    oss_access_key_id: Optional[str] = None
    oss_access_key_secret: Optional[str] = None
    # Local storage specific
    local_base_path: str = "/tmp/storage"
    # Advanced settings
    max_retry_attempts: int = 3
    timeout: int = 30
    enable_ssl: bool = True
    presign_max_size: int = 100 * 1024 * 1024  # 100MB
    presign_content_types: Optional[list[str]] = None
    validation_enabled: bool = False
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_types: Optional[list[str]] = None


class Settings(BaseSettings):
    """项目配置"""
    
    # 基础配置
    PROJECT_NAME: str = Field(default="FastAPI DDD User Management", env=["PROJECT_NAME", "APP_NAME"]) 
    VERSION: str = Field(default="1.0.0", env=["VERSION", "APP_VERSION"]) 
    DEBUG: bool = Field(default=True, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # 分组配置（方案A）：Kafka/Redis/Database/Storage 采用嵌套模型（外部类）
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    # 安全配置
    SECRET_KEY: Optional[str] = Field(
        default=None,
        env=["SECRET_KEY", "JWT_SECRET_KEY"],
        description="JWT签名密钥，生产环境必须设置"
    )
    ALGORITHM: str = Field(default="HS256", env=["ALGORITHM", "JWT_ALGORITHM"]) 
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env=["ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_EXPIRATION_MINUTES"])  # 30分钟
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7天
    
    # CORS配置
    CORS_ORIGINS: list = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    storage: StorageSettings = Field(default_factory=StorageSettings)

    # gRPC settings
    grpc: GrpcSettings = Field(default_factory=GrpcSettings)

    # 分页配置（支持环境变量覆盖）
    DEFAULT_PAGE_SIZE: int = Field(default=20, env="DEFAULT_PAGE_SIZE")
    MAX_PAGE_SIZE: int = Field(default=100, env="MAX_PAGE_SIZE")

    # 日志/请求体记录配置
    LOG_REQUEST_BODY_ENABLE_BY_DEFAULT: bool = Field(default=True, env="LOG_REQUEST_BODY_ENABLE_BY_DEFAULT")
    LOG_REQUEST_BODY_MAX_BYTES: int = Field(default=2048, env="LOG_REQUEST_BODY_MAX_BYTES")
    LOG_REQUEST_BODY_ALLOW_MULTIPART: bool = Field(default=False, env="LOG_REQUEST_BODY_ALLOW_MULTIPART")

    # 首个超管分布式锁配置
    FIRST_SUPERUSER_LOCK_TIMEOUT: int = Field(default=10, env="FIRST_SUPERUSER_LOCK_TIMEOUT")
    FIRST_SUPERUSER_LOCK_BLOCKING_TIMEOUT: int = Field(default=10, env="FIRST_SUPERUSER_LOCK_BLOCKING_TIMEOUT")

    # Redis 锁自动续租配置（全局默认值）
    REDIS_LOCK_AUTO_RENEW_DEFAULT: bool = Field(default=False, env="REDIS_LOCK_AUTO_RENEW_DEFAULT")
    REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO: float = Field(default=0.6, env="REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO")
    REDIS_LOCK_AUTO_RENEW_JITTER_RATIO: float = Field(default=0.1, env="REDIS_LOCK_AUTO_RENEW_JITTER_RATIO")

    # Realtime/WebSocket 配置
    REALTIME_WS_SEND_QUEUE_MAX: int = Field(default=100, env="REALTIME_WS_SEND_QUEUE_MAX")
    REALTIME_WS_SEND_OVERFLOW_POLICY: str = Field(
        default="drop_oldest", env="REALTIME_WS_SEND_OVERFLOW_POLICY",
        description="队列溢出策略: drop_oldest | drop_new | disconnect"
    )
    
    # Kafka grouped settings (builder below)
    
    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="allow",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def _validate_secret_key(self):
        # 所有环境均要求显式配置 SECRET_KEY（或 JWT_SECRET_KEY），避免热重载导致 Token 失效
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY 未配置。请在环境变量或 .env 中设置 SECRET_KEY（或 JWT_SECRET_KEY）"
            )
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        """允许 JSON 字符串或逗号分隔字符串两种格式。"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                import json
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return arr
                except Exception:
                    pass
            if "," in s:
                return [item.strip() for item in s.split(",") if item.strip()]
            return [s]
        return v


settings = Settings()
