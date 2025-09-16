"""
用户数据库模型 - SQLAlchemy ORM模型
注意：这是基础设施层的实现细节，不是领域模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime, timezone

from .base import Base


class UserModel(Base):
    """
    用户数据库模型
    
    这是数据库表的映射，不包含业务逻辑
    所有业务规则都在 domain.user.entity.User 中
    """
    __tablename__ = "users"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 用户基本信息
    username = Column(String(20), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    full_name = Column(String(100), nullable=True, comment="全名")
    
    # 认证信息
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    
    # 状态信息
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    is_superuser = Column(Boolean, default=False, nullable=False, comment="是否超级管理员")
    
    # 时间信息
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )
    last_login = Column(DateTime(timezone=True), nullable=True, comment="最后登录时间")
    
    def __repr__(self):
        return f"<UserModel(id={self.id}, username='{self.username}', email='{self.email}')>"
