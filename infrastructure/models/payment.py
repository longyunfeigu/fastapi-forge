"""
支付数据库模型 - SQLAlchemy ORM模型
注意：这是基础设施层的实现细节，不是领域模型
"""
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Text, JSON,
    Index, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base


class PaymentModel(Base):
    """
    支付数据库模型

    这是数据库表的映射，不包含业务逻辑
    所有业务规则都在 domain.payment.entity.Payment 中
    """
    __tablename__ = "payments"

    # 主键
    id = Column(Integer, primary_key=True, index=True)

    # 订单信息
    order_id = Column(String(100), unique=True, index=True, nullable=False, comment="订单ID")
    user_id = Column(Integer, nullable=True, index=True, comment="用户ID")

    # 支付渠道信息
    provider = Column(String(50), nullable=False, index=True, comment="支付提供商: stripe/alipay/wechat")
    provider_ref = Column(String(200), nullable=True, index=True, comment="支付渠道的支付ID")
    scene = Column(String(50), nullable=False, comment="支付场景: qr_code/wap/app等")

    # 金额信息（使用 Numeric 存储精确金额）
    amount = Column(Numeric(precision=15, scale=2), nullable=False, comment="支付金额")
    currency = Column(String(3), nullable=False, default="CNY", comment="货币代码 ISO-4217")

    # 退款信息
    refunded_amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="已退款金额"
    )
    refund_count = Column(Integer, nullable=False, default=0, comment="退款次数")

    # 状态
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="支付状态: pending/processing/succeeded/failed/canceled/refunding/refunded/partial_refunded"
    )

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )
    paid_at = Column(DateTime(timezone=True), nullable=True, comment="支付完成时间")
    canceled_at = Column(DateTime(timezone=True), nullable=True, comment="取消时间")

    # 回调URL
    notify_url = Column(String(500), nullable=True, comment="异步通知URL")
    return_url = Column(String(500), nullable=True, comment="同步跳转URL")

    # 前端凭证
    client_secret = Column(String(500), nullable=True, comment="客户端密钥（用于前端调用）")

    # 失败原因
    failure_reason = Column(Text, nullable=True, comment="失败原因")

    # 元数据（JSON格式，使用 extra_metadata 避免与 SQLAlchemy 的 metadata 冲突）
    extra_metadata = Column("metadata", JSON, nullable=True, comment="扩展元数据")

    # 关系
    refunds = relationship("RefundModel", back_populates="payment", lazy="select")

    # 索引
    __table_args__ = (
        Index("ix_payments_user_status", "user_id", "status"),
        Index("ix_payments_provider_ref", "provider", "provider_ref"),
        Index("ix_payments_created_at", "created_at"),
    )

    def __repr__(self):
        return (
            f"<PaymentModel(id={self.id}, order_id='{self.order_id}', "
            f"provider='{self.provider}', amount={self.amount}, status='{self.status}')>"
        )


class RefundModel(Base):
    """
    退款数据库模型

    退款作为支付聚合的一部分，记录支付的退款明细
    """
    __tablename__ = "refunds"

    # 主键
    id = Column(Integer, primary_key=True, index=True)

    # 关联支付
    payment_id = Column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的支付ID"
    )

    # 订单信息（冗余，便于查询）
    order_id = Column(String(100), index=True, nullable=False, comment="订单ID")

    # 退款渠道信息
    provider = Column(String(50), nullable=False, comment="支付提供商")
    provider_refund_id = Column(String(200), nullable=True, index=True, comment="渠道退款ID")

    # 金额信息
    amount = Column(Numeric(precision=15, scale=2), nullable=False, comment="退款金额")
    currency = Column(String(3), nullable=False, default="CNY", comment="货币代码")

    # 状态
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="退款状态: pending/processing/succeeded/failed"
    )

    # 退款原因
    reason = Column(Text, nullable=True, comment="退款原因")

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )
    succeeded_at = Column(DateTime(timezone=True), nullable=True, comment="退款成功时间")
    failed_at = Column(DateTime(timezone=True), nullable=True, comment="退款失败时间")

    # 失败原因
    failure_reason = Column(Text, nullable=True, comment="失败原因")

    # 元数据（使用 extra_metadata 避免与 SQLAlchemy 的 metadata 冲突）
    extra_metadata = Column("metadata", JSON, nullable=True, comment="扩展元数据")

    # 关系
    payment = relationship("PaymentModel", back_populates="refunds")

    # 索引
    __table_args__ = (
        Index("ix_refunds_payment_status", "payment_id", "status"),
        Index("ix_refunds_order_id", "order_id"),
        Index("ix_refunds_provider_refund_id", "provider", "provider_refund_id"),
    )

    def __repr__(self):
        return (
            f"<RefundModel(id={self.id}, payment_id={self.payment_id}, "
            f"amount={self.amount}, status='{self.status}')>"
        )
