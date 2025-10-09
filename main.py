"""
FastAPI应用主入口
"""
from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html

from api.routes import user
from api.routes import storage as storage_routes
from api.routes import files as files_routes
from api.routes import payments as payments_routes
from api.routes import ws as ws_routes
from api.middleware import RequestIDMiddleware, LoggingMiddleware
from api.middleware.locale import LocaleMiddleware
from core.config import settings
from core.exceptions import register_exception_handlers
from core.response import success_response
from core.i18n import t
from core.logging_config import get_logger, configure_logging
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
from application.services.realtime_service import RealtimeService
from infrastructure.realtime.connection_manager import ConnectionManager
from infrastructure.realtime.brokers import (
    InMemoryRealtimeBroker,
    RedisRealtimeBroker,
    KafkaRealtimeBroker,
    RocketMQRealtimeBroker,
)


# 初始化日志：在入口处显式配置，避免模块导入时的副作用
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建数据库表（仅开发环境）。生产应使用 Alembic 迁移
    if settings.DEBUG:
        await create_tables()
        logger.info("database_initialized", message="Database tables created (development)")
    else:
        logger.info(
            "database_migrations_required",
            message="No auto-create in production, use Alembic migrations (alembic upgrade head)"
        )
    if settings.redis.url:
        try:
            await init_redis_client()
            logger.info("redis_cache_initialized", message="Redis cache initialized")
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
            message="Storage service initialized",
            provider=config.type,
            bucket=config.bucket,
        )
        # 执行健康检查
        from infrastructure.external.storage import get_storage_client
        storage = get_storage_client()
        if storage and await storage.health_check():
            logger.info("storage_health_check_passed", message="Storage health check passed")
    except Exception as exc:
        logger.error(
            "storage_init_failed",
            error=str(exc),
        )

    # 初始化实时通信（WebSocket）
    try:
        # 选择 Broker：根据 REALTIME_BROKER，默认 auto -> redis(if url) else inmemory
        provider = (settings.REALTIME_BROKER or "auto").lower()
        broker = None
        if provider == "kafka":
            try:
                if KafkaRealtimeBroker is None:
                    raise RuntimeError("Kafka broker not available (missing dependency)")
                broker = KafkaRealtimeBroker()
                logger.info("realtime_broker_selected", provider="kafka")
            except Exception as exc:
                logger.error("realtime_broker_init_failed", provider="kafka", error=str(exc))
        elif provider == "rocketmq":
            try:
                if RocketMQRealtimeBroker is None:
                    raise RuntimeError("RocketMQ broker not available (missing dependency)")
                broker = RocketMQRealtimeBroker()
                logger.info("realtime_broker_selected", provider="rocketmq")
            except Exception as exc:
                logger.error("realtime_broker_init_failed", provider="rocketmq", error=str(exc))
        elif provider == "redis" or provider == "auto":
            if settings.redis.url:
                broker = RedisRealtimeBroker()
                logger.info("realtime_broker_selected", provider="redis")
            elif provider == "redis":
                logger.warning("realtime_broker_redis_missing_url", message="REDIS__URL not set, falling back to in-memory broker")
        # 回退：内存版
        if broker is None:
            broker = InMemoryRealtimeBroker()
            logger.info("realtime_broker_selected", provider="inmemory")
        conn_mgr = ConnectionManager()
        realtime = RealtimeService(broker=broker, connections=conn_mgr)
        await broker.subscribe(realtime.on_broker_event)
        app.state.realtime_broker = broker
        app.state.realtime_connections = conn_mgr
        app.state.realtime_service = realtime
        logger.info("realtime_initialized")
    except Exception as exc:
        logger.error("realtime_init_failed", error=str(exc))
    
    yield
    # 关闭时的清理工作
    if settings.redis.url:
        await shutdown_redis_client()
        logger.info("redis_cache_shutdown", message="Redis cache shutdown")
    
    # 关闭存储服务
    await shutdown_storage_client()
    logger.info("storage_shutdown", message="Storage service shutdown")
    # 关闭实时通信
    broker = getattr(app.state, "realtime_broker", None)
    if broker is not None:
        close = getattr(broker, "aclose", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass
    logger.info("application_shutdown", message="Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    description="基于DDD架构的用户管理系统",
    docs_url=None,  # 使用自定义 Swagger UI 以支持国际化
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

# 2.5 语言中间件（解析 locale）
app.add_middleware(LocaleMiddleware)

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
app.include_router(ws_routes.router, prefix="/api/v1")


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
        message=t("welcome")
    )


# 健康检查
@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查端点"""
    return success_response(data={"status": "healthy"}, message=t("health.ok"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )


# 自定义 Swagger UI（支持国际化）
def _map_locale_to_swagger_lang(locale: str) -> str:
    """将后端 locale 映射为 Swagger UI 支持的语言代码。"""
    if not locale:
        return "en"
    tag = locale.replace("_", "-").lower()
    # 常见映射（根据 Swagger UI 语言包）
    if tag in {"zh", "zh-cn", "zh-hans"}:
        return "zh-CN"
    if tag in {"zh-tw", "zh-hant"}:
        return "zh-TW"
    if tag in {"en", "en-us", "en-gb"}:
        return "en"
    # 其他语言可按需扩展
    return "en"


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request) -> HTMLResponse:
    # 由 LocaleMiddleware 解析的语言，或从查询参数获取
    try:
        current = getattr(request.state, "locale", None)
    except Exception:
        current = None
    lang = _map_locale_to_swagger_lang(str(current or "en"))

    oauth_redirect_url = "/docs/oauth2-redirect"
    base = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.PROJECT_NAME} - API Docs",
        oauth2_redirect_url=oauth_redirect_url,
        init_oauth=app.swagger_ui_init_oauth,
        swagger_ui_parameters={
            # 关键：传入语言
            "lang": lang,
            # 常用增强参数（可按需调整）
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )
    # 注入 requestInterceptor：为“Try it out”请求附带语言信息
    try:
        content = base.body.decode("utf-8")
    except Exception:
        content = str(base.body)
    injection = (
        "requestInterceptor: function(req){\n"
        "  try {\n"
        "    const url = new URL(req.url, window.location.origin);\n"
        "    const params = new URLSearchParams(window.location.search);\n"
        "    const lang = params.get('lang') || localStorage.getItem('docs_lang') || '%s';\n"
        "    if (lang) {\n"
        "      req.headers = req.headers || {};\n"
        "      req.headers['X-Lang'] = lang;\n"
        "      url.searchParams.set('lang', lang);\n"
        "      req.url = url.toString();\n"
        "    }\n"
        "  } catch (e) {}\n"
        "  return req;\n"
        "},"
    ) % (lang,)
    content = content.replace("SwaggerUIBundle({", "SwaggerUIBundle({\n  " + injection, 1)
    # 记住当前语言（刷新仍能保留）
    remember_lang_script = (
        "<script>\n"
        "(function(){\n"
        "  try {\n"
        "    var p = new URLSearchParams(window.location.search);\n"
        "    var l = p.get('lang');\n"
        "    if (l) localStorage.setItem('docs_lang', l);\n"
        "  } catch (e) {}\n"
        "})();\n"
        "</script>"
    )
    content = content.replace("</body>", remember_lang_script + "\n</body>")
    # 返回新的 HTMLResponse，避免沿用旧的 Content-Length 头
    return HTMLResponse(content=content, status_code=base.status_code)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()
