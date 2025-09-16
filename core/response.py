"""
统一响应格式定义
"""
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel, field_serializer
from datetime import datetime
from enum import IntEnum


T = TypeVar("T")


class BusinessCode(IntEnum):
    """业务状态码定义"""
    
    # 成功
    SUCCESS = 0
    
    # 参数错误 (1xxxx)
    PARAM_ERROR = 10000
    PARAM_MISSING = 10001
    PARAM_TYPE_ERROR = 10002
    PARAM_VALIDATION_ERROR = 10003
    
    # 业务错误 (2xxxx)
    BUSINESS_ERROR = 20000
    USER_NOT_FOUND = 20001
    USER_ALREADY_EXISTS = 20002
    PASSWORD_ERROR = 20003
    TOKEN_INVALID = 20004
    TOKEN_EXPIRED = 20005
    
    # 权限错误 (3xxxx)
    PERMISSION_ERROR = 30000
    UNAUTHORIZED = 30001
    FORBIDDEN = 30002
    
    # 系统错误 (4xxxx)
    SYSTEM_ERROR = 40000
    DATABASE_ERROR = 40001
    NETWORK_ERROR = 40002
    SERVICE_UNAVAILABLE = 40003
    
    # 限流错误 (5xxxx)
    RATE_LIMIT_ERROR = 50000
    TOO_MANY_REQUESTS = 50001


class ErrorDetail(BaseModel):
    """错误详情"""
    type: str
    details: Optional[dict] = None
    field: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime) -> str:
        """序列化时间戳"""
        return timestamp.isoformat()


class Response(BaseModel, Generic[T]):
    """统一响应模型"""
    code: int
    message: str
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据模型"""
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def success_response(
    data: Any = None,
    message: str = "Success",
    code: int = BusinessCode.SUCCESS
) -> Response:
    """
    创建成功响应
    
    Args:
        data: 返回数据
        message: 成功消息
        code: 业务状态码
        
    Returns:
        Response: 统一响应对象
    """
    return Response(
        code=code,
        message=message,
        data=data,
        error=None
    )


def error_response(
    code: int,
    message: str,
    error_type: str = "BusinessError",
    details: Optional[dict] = None,
    field: Optional[str] = None,
    request_id: Optional[str] = None
) -> Response:
    """
    创建错误响应
    
    Args:
        code: 业务状态码
        message: 错误消息
        error_type: 错误类型
        details: 错误详情
        field: 错误字段
        request_id: 请求ID
        
    Returns:
        Response: 统一响应对象
    """
    return Response(
        code=code,
        message=message,
        data=None,
        error=ErrorDetail(
            type=error_type,
            details=details,
            field=field,
            request_id=request_id
        )
    )


def paginated_response(
    items: list,
    total: int,
    page: int,
    size: int,
    message: str = "Success"
) -> Response[PaginatedData]:
    """
    创建分页响应
    
    Args:
        items: 数据列表
        total: 总数
        page: 当前页
        size: 每页大小
        message: 成功消息
        
    Returns:
        Response: 统一响应对象
    """
    pages = (total + size - 1) // size if size > 0 else 0
    
    return Response(
        code=BusinessCode.SUCCESS,
        message=message,
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        ),
        error=None
    )