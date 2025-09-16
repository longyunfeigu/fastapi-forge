"""
自定义异常类和全局异常处理器
"""
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
import traceback
import uuid
from datetime import datetime

from .response import error_response, BusinessCode


class BusinessException(Exception):
    """业务异常基类"""
    
    def __init__(
        self,
        code: int,
        message: str,
        error_type: str = "BusinessError",
        details: Optional[dict] = None,
        field: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.error_type = error_type
        self.details = details
        self.field = field
        super().__init__(self.message)


class UserNotFoundException(BusinessException):
    """用户不存在异常"""
    
    def __init__(self, user_id: Optional[str] = None):
        details = {"user_id": user_id} if user_id else None
        super().__init__(
            code=BusinessCode.USER_NOT_FOUND,
            message="用户不存在",
            error_type="UserNotFound",
            details=details
        )


class UserAlreadyExistsException(BusinessException):
    """用户已存在异常"""
    
    def __init__(self, email: str):
        super().__init__(
            code=BusinessCode.USER_ALREADY_EXISTS,
            message=f"邮箱 {email} 已被注册",
            error_type="UserAlreadyExists",
            details={"email": email},
            field="email"
        )


class UnauthorizedException(BusinessException):
    """未授权异常"""
    
    def __init__(self, message: str = "未授权访问"):
        super().__init__(
            code=BusinessCode.UNAUTHORIZED,
            message=message,
            error_type="Unauthorized"
        )


class TokenExpiredException(BusinessException):
    """Token过期异常"""
    
    def __init__(self):
        super().__init__(
            code=BusinessCode.TOKEN_EXPIRED,
            message="Token已过期",
            error_type="TokenExpired"
        )


class PasswordErrorException(BusinessException):
    """密码错误异常"""
    
    def __init__(self):
        super().__init__(
            code=BusinessCode.PASSWORD_ERROR,
            message="用户名或密码错误",
            error_type="PasswordError"
        )


class RateLimitException(BusinessException):
    """限流异常"""
    
    def __init__(self, retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            code=BusinessCode.TOO_MANY_REQUESTS,
            message="请求过于频繁，请稍后重试",
            error_type="RateLimit",
            details=details
        )


def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理器
    
    Args:
        app: FastAPI应用实例
    """
    
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        """处理业务异常"""
        request_id = str(uuid.uuid4())
        response = error_response(
            code=exc.code,
            message=exc.message,
            error_type=exc.error_type,
            details=exc.details,
            field=exc.field,
            request_id=request_id
        )
        return JSONResponse(
            status_code=200,  # 业务异常统一返回200，通过code字段区分
            content=response.model_dump(mode='json')
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理参数验证异常"""
        request_id = str(uuid.uuid4())
        errors = exc.errors()
        
        # 提取第一个错误的详细信息
        first_error = errors[0] if errors else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", [])[1:])
        
        response = error_response(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message=f"参数验证失败: {first_error.get('msg', '未知错误')}",
            error_type="ValidationError",
            details={"errors": errors},
            field=field,
            request_id=request_id
        )
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode='json')
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理HTTP异常"""
        request_id = str(uuid.uuid4())
        
        # 映射HTTP状态码到业务码
        code_mapping = {
            401: BusinessCode.UNAUTHORIZED,
            403: BusinessCode.FORBIDDEN,
            404: BusinessCode.USER_NOT_FOUND,
            429: BusinessCode.TOO_MANY_REQUESTS,
            500: BusinessCode.SYSTEM_ERROR,
            503: BusinessCode.SERVICE_UNAVAILABLE
        }
        
        code = code_mapping.get(exc.status_code, BusinessCode.SYSTEM_ERROR)
        
        response = error_response(
            code=code,
            message=exc.detail,
            error_type="HTTPError",
            details={"status_code": exc.status_code},
            request_id=request_id
        )
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode='json')
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        request_id = str(uuid.uuid4())
        
        # 在开发环境可以返回详细错误信息
        details = None
        if app.debug:
            details = {
                "exception": str(exc),
                "traceback": traceback.format_exc()
            }
        
        response = error_response(
            code=BusinessCode.SYSTEM_ERROR,
            message="系统内部错误",
            error_type="SystemError",
            details=details,
            request_id=request_id
        )
        
        # 记录日志
        print(f"[{datetime.utcnow()}] Request ID: {request_id}")
        print(f"Error: {exc}")
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode='json')
        )