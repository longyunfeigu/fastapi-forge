"""
FastAPI应用主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import user
from api.routes import storage as storage_routes
from api.routes import files as files_routes
from api.routes import payments as payments_routes
from api.middleware import RequestIDMiddleware, LoggingMiddleware
from core.config import settings
from core.exceptions import register_exception_handlers
from core.response import success_response
from core.logging_config import get_logger
from infrastructure.database import create_tables
from infrastructure.external.cache import (
    init_redis_client,
    shutdown_redis_client,
)
from infrastructure.external.storage import (
    init_storage_client,
    shutdown_storage_client,
    get_storage_config,
    StorageType
)


# 获取logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建数据库表（仅开发环境）。生产应使用 Alembic 迁移
    if settings.DEBUG:
        await create_tables()
        logger.info("database_initialized", message="数据库表创建完成 (development)")
    else:
        logger.info(
            "database_migrations_required",
            message="生产环境不自动建表，请使用 Alembic 迁移 (alembic upgrade head)"
        )
    if settings.redis.url:
        try:
            await init_redis_client()
            logger.info("redis_cache_initialized", message="Redis缓存初始化完成")
        except Exception as exc:
            logger.error(
                "redis_cache_init_failed",
                error=str(exc)
            )
    
    # 初始化存储服务（根据配置自动选择 provider；本地为默认）
    try:
        await init_storage_client()
        config = get_storage_config()
        logger.info(
            "storage_initialized",
            message="存储服务初始化完成",
            provider=config.type,
            bucket=config.bucket,
        )
        # 执行健康检查
        from infrastructure.external.storage import get_storage_client
        storage = get_storage_client()
        if storage and await storage.health_check():
            logger.info("storage_health_check_passed", message="存储服务健康检查通过")
    except Exception as exc:
        logger.error(
            "storage_init_failed",
            error=str(exc),
        )
    
    yield
    # 关闭时的清理工作
    if settings.redis.url:
        await shutdown_redis_client()
        logger.info("redis_cache_shutdown", message="Redis缓存已关闭")
    
    # 关闭存储服务
    await shutdown_storage_client()
    logger.info("storage_shutdown", message="存储服务已关闭")
    logger.info("application_shutdown", message="应用关闭")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    description="基于DDD架构的用户管理系统",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.PROJECT_NAME,
    }
)

# 添加中间件（注意顺序：从下往上执行）
# 1. Request ID中间件（最先执行，为后续中间件提供request_id）
app.add_middleware(RequestIDMiddleware)

# 2. 日志中间件（依赖request_id）
app.add_middleware(LoggingMiddleware)

# 3. CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
register_exception_handlers(app)


# 注册路由
app.include_router(user.router, prefix="/api/v1")
app.include_router(storage_routes.router, prefix="/api/v1")
app.include_router(files_routes.router, prefix="/api/v1")
app.include_router(payments_routes.router, prefix="/api/v1")


# 根路径
@app.get("/", tags=["Root"])
async def root():
    """API根路径"""
    return success_response(
        data={
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "redoc": "/redoc"
        },
        message="Welcome to FastAPI Forge"
    )


# 健康检查
@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查端点"""
    return success_response(
        data={"status": "healthy"},
        message="Service is healthy"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
