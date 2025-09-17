"""
配置文件 - 项目配置管理
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from pydantic import model_validator


class Settings(BaseSettings):
    """项目配置"""
    
    # 基础配置
    PROJECT_NAME: str = Field(default="FastAPI DDD User Management", env=["PROJECT_NAME", "APP_NAME"]) 
    VERSION: str = Field(default="1.0.0", env=["VERSION", "APP_VERSION"]) 
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost/userdb",
        env="DATABASE_URL"
    )
    
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
    
    # 缓存配置
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    CACHE_DEFAULT_TTL: int = Field(default=300, env="CACHE_DEFAULT_TTL")
    CACHE_NAMESPACE: str = Field(default="fastapi-forge", env="CACHE_NAMESPACE")

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
    
    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
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
