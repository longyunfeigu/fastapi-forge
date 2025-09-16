"""
数据传输对象（DTO）- 应用层与表现层之间的数据传输
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserCreateDTO(BaseModel):
    """用户创建DTO"""
    username: str = Field(..., min_length=3, max_length=20, 
                         description="用户名，3-20个字符")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码，至少8位")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$', 
                                 description="手机号（中国）")
    
    @validator('username')
    def validate_username(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v


class UserUpdateDTO(BaseModel):
    """用户更新DTO"""
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')


class UserResponseDTO(BaseModel):
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
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LoginDTO(BaseModel):
    """登录DTO"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenDTO(BaseModel):
    """令牌DTO"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


class ChangePasswordDTO(BaseModel):
    """修改密码DTO"""
    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=8, description="新密码")
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not any(c.islower() for c in v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含至少一个数字')
        return v


class PaginationParams(BaseModel):
    """分页参数"""
    skip: int = Field(0, ge=0, description="跳过记录数")
    limit: int = Field(100, ge=1, le=1000, description="返回记录数")


class MessageDTO(BaseModel):
    """消息响应DTO"""
    message: str
    code: int = 200
    
    
class ErrorDTO(BaseModel):
    """错误响应DTO"""
    error: str
    code: int
    detail: Optional[str] = None