"""
配置文件 - 项目配置管理
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import secrets


class Settings(BaseSettings):
    """项目配置"""
    
    # 基础配置
    PROJECT_NAME: str = "FastAPI DDD User Management"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost/userdb",
        env="DATABASE_URL"
    )
    
    # 安全配置
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        env="SECRET_KEY"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30分钟
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

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()
