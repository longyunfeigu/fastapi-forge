"""
用户领域事件 - 记录重要的业务事件
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class UserCreated:
    """用户创建事件"""
    user_id: int
    username: str
    email: str
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserActivated:
    """用户激活事件"""
    user_id: int
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserDeactivated:
    """用户停用事件"""
    user_id: int
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PasswordChanged:
    """密码修改事件"""
    user_id: int
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserProfileUpdated:
    """用户资料更新事件"""
    user_id: int
    updated_fields: list
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserDeleted:
    """用户删除事件"""
    user_id: int
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SuperuserGranted:
    """授予超级管理员权限事件"""
    user_id: int
    granted_by: int  # 授权人ID
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SuperuserRevoked:
    """撤销超级管理员权限事件"""
    user_id: int
    revoked_by: int  # 撤销人ID
    event_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
