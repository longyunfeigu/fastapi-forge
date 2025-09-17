"""
数据传输对象（DTO）- 应用层与表现层之间的数据传输
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, model_serializer, ConfigDict
from shared.codes import BusinessCode
from typing import Optional
from datetime import datetime, timezone
from core.config import settings


class DTOBase(BaseModel):
    """Base DTO: unify datetime serialization to UTC-Z for all subclasses."""

    @model_serializer(mode="wrap")
    def _serialize_model(self, handler):  # type: ignore[override]
        data = handler(self)

        def convert(value):
            if isinstance(value, datetime):
                ts = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                s = ts.astimezone(timezone.utc).isoformat()
                return s.replace("+00:00", "Z")
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, tuple):
                return tuple(convert(v) for v in value)
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value

        return convert(data)


class UserCreateDTO(DTOBase):
    """用户创建DTO"""
    username: str = Field(..., min_length=3, max_length=20, 
                         description="用户名，3-20个字符")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码，至少8位")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$', 
                                 description="手机号（中国）")
    
    @field_validator('username')
    def validate_username(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v


class UserUpdateDTO(DTOBase):
    """用户更新DTO"""
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')


class UserResponseDTO(DTOBase):
    """用户响应DTO"""
    id: int
    username: str
    email: str
    phone: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class LoginDTO(DTOBase):
    """登录DTO"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenDTO(DTOBase):
    """令牌DTO"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


class RefreshTokenDTO(DTOBase):
    """刷新令牌请求 DTO"""
    refresh_token: str


class ChangePasswordDTO(DTOBase):
    """修改密码DTO"""
    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=8, description="新密码")
    
    @field_validator('new_password')
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not any(c.islower() for c in v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含至少一个数字')
        return v


class PaginationParams(DTOBase):
    """分页参数（页码/每页大小），自动派生 skip/limit"""
    page: int = Field(1, ge=1, description="页码，从1开始")
    size: int = Field(
        default=settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="每页大小",
    )

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class MessageDTO(DTOBase):
    """消息响应DTO"""
    message: str
    code: int = BusinessCode.SUCCESS
    
    
class ErrorDTO(DTOBase):
    """错误响应DTO"""
    error: str
    code: int
    detail: Optional[str] = None
