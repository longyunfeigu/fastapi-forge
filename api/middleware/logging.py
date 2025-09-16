"""
请求/响应日志中间件
记录所有HTTP请求和响应，包括耗时统计
"""
import time
from typing import Callable
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging_config import get_logger
from api.middleware.request_id import set_user_id


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志记录中间件
    
    功能：
    1. 记录请求信息（方法、路径、参数等）
    2. 记录响应信息（状态码、耗时等）
    3. 记录异常信息
    4. 统计请求处理时间
    """
    
    # 跳过日志的路径
    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
    
    # 敏感字段，日志中需要脱敏
    SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "access_token", "refresh_token"}
    
    async def dispatch(self, request: Request, call_next):
        # 检查是否需要跳过日志
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取请求信息
        request_info = await self._get_request_info(request)
        
        # 记录请求日志
        logger.info(
            "request_started",
            **request_info
        )
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration = time.time() - start_time
            
            # 记录响应日志
            self._log_response(response, duration, request_info)
            
            # 在响应头中添加处理时间
            response.headers["X-Process-Time"] = f"{duration:.3f}"
            
            return response
            
        except Exception as exc:
            # 计算耗时
            duration = time.time() - start_time
            
            # 记录异常日志
            logger.error(
                "request_failed",
                duration=duration,
                error=str(exc),
                error_type=type(exc).__name__,
                **request_info,
                exc_info=True
            )
            
            # 重新抛出异常，让异常处理器处理
            raise
    
    async def _get_request_info(self, request: Request) -> dict:
        """
        获取请求信息
        
        Args:
            request: FastAPI请求对象
            
        Returns:
            请求信息字典
        """
        # 基本信息
        info = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
        }
        
        # 添加路径参数
        if hasattr(request, "path_params"):
            info["path_params"] = request.path_params
        
        # 添加请求体（仅限POST/PUT/PATCH）
        # 注意：暂时不读取body，因为会导致后续处理器无法读取
        # TODO: 实现body的正确缓存和重放机制
        if request.method in ["POST", "PUT", "PATCH"]:
            info["has_body"] = True
        
        # 添加用户代理
        user_agent = request.headers.get("User-Agent")
        if user_agent:
            info["user_agent"] = user_agent
        
        # 添加来源
        referer = request.headers.get("Referer")
        if referer:
            info["referer"] = referer
        
        return info
    
    def _log_response(self, response: Response, duration: float, request_info: dict):
        """
        记录响应日志
        
        Args:
            response: FastAPI响应对象
            duration: 请求处理时间
            request_info: 请求信息
        """
        # 根据状态码选择日志级别
        status_code = response.status_code
        
        log_data = {
            "status_code": status_code,
            "duration": duration,
            **request_info
        }
        
        if status_code < 400:
            # 成功响应
            logger.info("request_completed", **log_data)
        elif status_code < 500:
            # 客户端错误
            logger.warning("request_client_error", **log_data)
        else:
            # 服务器错误
            logger.error("request_server_error", **log_data)
    
    def _sanitize_data(self, data: any) -> any:
        """
        脱敏处理敏感数据
        
        Args:
            data: 原始数据
            
        Returns:
            脱敏后的数据
        """
        if isinstance(data, dict):
            # 处理字典
            sanitized = {}
            for key, value in data.items():
                if key.lower() in self.SENSITIVE_FIELDS:
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            # 处理列表
            return [self._sanitize_data(item) for item in data]
        else:
            # 其他类型直接返回
            return data


class AccessLogMiddleware:
    """
    访问日志中间件（轻量级）
    仅记录访问日志，不记录详细的请求/响应信息
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time
                
                # 记录访问日志
                logger.info(
                    "access",
                    method=scope["method"],
                    path=scope["path"],
                    status=message["status"],
                    duration=duration
                )
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)