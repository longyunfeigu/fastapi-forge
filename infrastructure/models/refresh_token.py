"""
刷新令牌数据库模型 - SQLAlchemy ORM模型
支持令牌轮转（Refresh Token Rotation）
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base


class RefreshTokenModel(Base):
    """
    刷新令牌数据库模型

    实现刷新令牌轮转（Refresh Token Rotation）：
    - 每次使用刷新令牌时，旧令牌失效，生成新令牌
    - 防止令牌重放攻击
    - 支持令牌撤销（revocation）
    - 检测令牌家族链中的异常使用
    """
    __tablename__ = "refresh_tokens"

    # 主键
    id = Column(Integer, primary_key=True, index=True)

    # 令牌标识（JTI - JWT Token Identifier）
    jti = Column(String(64), unique=True, index=True, nullable=False, comment="令牌唯一标识符")

    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # 令牌家族（Token Family）- 用于检测令牌重用
    family_id = Column(String(64), index=True, nullable=False, comment="令牌家族ID，同一登录会话共享")

    # 前驱令牌（用于检测重放攻击）
    parent_jti = Column(String(64), nullable=True, index=True, comment="父令牌JTI，用于追踪令牌链")

    # 令牌哈希（存储令牌哈希而非明文）
    token_hash = Column(String(128), nullable=False, comment="令牌SHA-256哈希")

    # 状态
    is_revoked = Column(Boolean, default=False, nullable=False, index=True, comment="是否已撤销")
    is_used = Column(Boolean, default=False, nullable=False, comment="是否已使用（轮转后标记）")

    # 设备信息（可选，用于安全审计）
    device_info = Column(Text, nullable=True, comment="设备信息（User-Agent等）")
    ip_address = Column(String(45), nullable=True, comment="IP地址（支持IPv6）")

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="创建时间"
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="过期时间"
    )
    used_at = Column(DateTime(timezone=True), nullable=True, comment="使用时间")
    revoked_at = Column(DateTime(timezone=True), nullable=True, comment="撤销时间")

    # 撤销原因
    revoke_reason = Column(String(200), nullable=True, comment="撤销原因")

    # 关系
    # user = relationship("UserModel", back_populates="refresh_tokens")

    # 索引
    __table_args__ = (
        Index("ix_refresh_tokens_user_active", "user_id", "is_revoked", "is_used"),
        Index("ix_refresh_tokens_family_active", "family_id", "is_revoked"),
        Index("ix_refresh_tokens_expires", "expires_at", "is_revoked"),
    )

    def __repr__(self):
        return (
            f"<RefreshTokenModel(id={self.id}, jti='{self.jti}', "
            f"user_id={self.user_id}, is_revoked={self.is_revoked}, is_used={self.is_used})>"
        )
