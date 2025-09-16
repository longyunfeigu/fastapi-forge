"""
用户领域实体 - 包含核心业务规则
"""
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass
import re
import hashlib


@dataclass
class User:
    """用户实体 - 领域核心"""
    
    id: Optional[int]
    username: str
    email: str
    phone: Optional[str]
    full_name: Optional[str]
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化后的业务规则验证"""
        self.validate_email()
        self.validate_username()
        if self.phone:
            self.validate_phone()
    
    def validate_email(self) -> None:
        """业务规则：邮箱格式验证"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.email):
            raise ValueError(f"无效的邮箱格式: {self.email}")
    
    def validate_username(self) -> None:
        """业务规则：用户名验证"""
        if len(self.username) < 3:
            raise ValueError("用户名至少需要3个字符")
        if len(self.username) > 20:
            raise ValueError("用户名不能超过20个字符")
        if not re.match(r'^[a-zA-Z0-9_]+$', self.username):
            raise ValueError("用户名只能包含字母、数字和下划线")
    
    def validate_phone(self) -> None:
        """业务规则：手机号验证（中国手机号）"""
        if self.phone:
            phone_pattern = r'^1[3-9]\d{9}$'
            if not re.match(phone_pattern, self.phone):
                raise ValueError(f"无效的手机号格式: {self.phone}")
    
    def activate(self) -> None:
        """业务规则：激活用户"""
        if self.is_active:
            raise ValueError("用户已经是激活状态")
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc)
    
    def deactivate(self) -> None:
        """业务规则：停用用户"""
        if not self.is_active:
            raise ValueError("用户已经是停用状态")
        if self.is_superuser:
            raise ValueError("不能停用超级管理员账户")
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)
    
    def update_profile(self, full_name: Optional[str] = None, 
                       phone: Optional[str] = None) -> None:
        """业务规则：更新用户资料"""
        if full_name is not None:
            self.full_name = full_name
        if phone is not None:
            self.phone = phone
            self.validate_phone()
        self.updated_at = datetime.now(timezone.utc)
    
    def change_password(self, new_password_hash: str) -> None:
        """业务规则：修改密码"""
        if not new_password_hash:
            raise ValueError("密码不能为空")
        self.hashed_password = new_password_hash
        self.updated_at = datetime.now(timezone.utc)
    
    def record_login(self) -> None:
        """业务规则：记录登录时间"""
        self.last_login = datetime.now(timezone.utc)
    
    def grant_superuser(self) -> None:
        """业务规则：授予超级管理员权限"""
        if not self.is_active:
            raise ValueError("不能给停用的用户授予超级管理员权限")
        self.is_superuser = True
        self.updated_at = datetime.now(timezone.utc)
    
    def revoke_superuser(self) -> None:
        """业务规则：撤销超级管理员权限"""
        self.is_superuser = False
        self.updated_at = datetime.now(timezone.utc)
