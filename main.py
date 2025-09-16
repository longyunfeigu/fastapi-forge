"""
FastAPI应用主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager

from api.routes import user
from api.middleware import RequestIDMiddleware, LoggingMiddleware
from core.config import settings
from core.exceptions import register_exception_handlers
from core.response import success_response
from core.logging_config import get_logger
from infrastructure.database import create_tables
from infrastructure.cache import init_redis_cache, shutdown_redis_cache


# 获取logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建数据库表
    await create_tables()
    logger.info("database_initialized", message="数据库表创建完成")
    if settings.REDIS_URL:
        try:
            await init_redis_cache()
            logger.info("redis_cache_initialized", message="Redis缓存初始化完成")
        except Exception as exc:
            logger.error(
                "redis_cache_init_failed",
                error=str(exc)
            )
    yield
    # 关闭时的清理工作
    if settings.REDIS_URL:
        await shutdown_redis_cache()
        logger.info("redis_cache_shutdown", message="Redis缓存已关闭")
    logger.info("application_shutdown", message="应用关闭")


# 配置JWT Bearer认证
bearer_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Enter: **Bearer &lt;token&gt;**",
    auto_error=False
)

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
