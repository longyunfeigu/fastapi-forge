"""
支付领域实体 - 支付聚合根
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Literal
from enum import Enum

from domain.common.exceptions import DomainValidationException


class PaymentStatus(str, Enum):
    """支付状态枚举"""
    PENDING = "pending"           # 待支付
    PROCESSING = "processing"     # 处理中
    SUCCEEDED = "succeeded"       # 支付成功
    FAILED = "failed"            # 支付失败
    CANCELED = "canceled"        # 已取消
    REFUNDING = "refunding"      # 退款中
    REFUNDED = "refunded"        # 已退款
    PARTIAL_REFUNDED = "partial_refunded"  # 部分退款


class RefundStatus(str, Enum):
    """退款状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """确保时间为 UTC 时区"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Payment:
    """
    支付聚合根 - 管理支付生命周期

    业务规则：
    1. 订单ID + 提供商组合必须唯一
    2. 金额必须大于0
    3. 状态转换必须遵循状态机
    4. 退款金额不能超过支付金额
    5. 只有成功的支付才能退款
    """

    id: Optional[int]
    order_id: str
    user_id: Optional[int]
    provider: str  # stripe, alipay, wechat
    provider_ref: Optional[str]  # 支付渠道的支付ID
    amount: Decimal
    currency: str  # ISO-4217
    status: PaymentStatus
    scene: str  # qr_code, wap, app, etc.

    # 退款相关
    refunded_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    refund_count: int = 0

    # 时间戳
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

    # 可选字段
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    client_secret: Optional[str] = None  # 前端调用凭证
    failure_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """初始化后验证"""
        self._validate_amount()
        self._validate_currency()
        self._normalize_timestamps()
        if self.metadata is None:
            self.metadata = {}

    def _validate_amount(self) -> None:
        """业务规则：金额必须大于0"""
        if self.amount <= 0:
            raise DomainValidationException(
                f"支付金额必须大于0: {self.amount}",
                field="amount"
            )

    def _validate_currency(self) -> None:
        """业务规则：货币代码必须是3位字母"""
        if not self.currency or len(self.currency) != 3 or not self.currency.isalpha():
            raise DomainValidationException(
                f"无效的货币代码: {self.currency}",
                field="currency"
            )

    def _normalize_timestamps(self) -> None:
        """规范化所有时间戳为 UTC"""
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        self.paid_at = _ensure_utc(self.paid_at)
        self.canceled_at = _ensure_utc(self.canceled_at)

    def mark_processing(self) -> None:
        """标记为处理中"""
        if self.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 processing",
                field="status"
            )
        self.status = PaymentStatus.PROCESSING
        self.updated_at = datetime.now(timezone.utc)

    def mark_succeeded(self, provider_ref: Optional[str] = None) -> None:
        """
        标记支付成功

        业务规则：只能从 pending 或 processing 转为 succeeded
        """
        if self.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 succeeded",
                field="status"
            )
        self.status = PaymentStatus.SUCCEEDED
        if provider_ref:
            self.provider_ref = provider_ref
        self.paid_at = datetime.now(timezone.utc)
        self.updated_at = self.paid_at
        self.failure_reason = None

    def mark_failed(self, reason: Optional[str] = None) -> None:
        """
        标记支付失败

        业务规则：只能从 pending 或 processing 转为 failed
        """
        if self.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 failed",
                field="status"
            )
        self.status = PaymentStatus.FAILED
        self.failure_reason = reason
        self.updated_at = datetime.now(timezone.utc)

    def mark_canceled(self) -> None:
        """
        取消支付

        业务规则：只能取消待支付或失败的订单
        """
        if self.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
            raise DomainValidationException(
                f"无法取消状态为 {self.status} 的支付",
                field="status"
            )
        self.status = PaymentStatus.CANCELED
        self.canceled_at = datetime.now(timezone.utc)
        self.updated_at = self.canceled_at

    def can_refund(self) -> bool:
        """检查是否可以退款"""
        return (
            self.status in (PaymentStatus.SUCCEEDED, PaymentStatus.PARTIAL_REFUNDED)
            and self.refunded_amount < self.amount
        )

    def calculate_refundable_amount(self) -> Decimal:
        """计算可退款金额"""
        return self.amount - self.refunded_amount

    def apply_refund(self, refund_amount: Decimal) -> None:
        """
        应用退款

        业务规则：
        1. 只有成功或部分退款的支付才能退款
        2. 退款金额不能超过剩余可退金额
        """
        if not self.can_refund():
            raise DomainValidationException(
                f"支付状态为 {self.status}，无法退款",
                field="status"
            )

        if refund_amount <= 0:
            raise DomainValidationException(
                f"退款金额必须大于0: {refund_amount}",
                field="refund_amount"
            )

        refundable = self.calculate_refundable_amount()
        if refund_amount > refundable:
            raise DomainValidationException(
                f"退款金额 {refund_amount} 超过可退金额 {refundable}",
                field="refund_amount"
            )

        self.refunded_amount += refund_amount
        self.refund_count += 1
        self.updated_at = datetime.now(timezone.utc)

        # 更新状态
        if self.refunded_amount >= self.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIAL_REFUNDED

    def is_final_status(self) -> bool:
        """检查是否为终态"""
        return self.status in (
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELED,
            PaymentStatus.REFUNDED
        )

    def update_metadata(self, key: str, value: any) -> None:
        """更新元数据"""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class Refund:
    """
    退款实体 - Payment 聚合的一部分

    业务规则：
    1. 退款金额不能超过原支付金额
    2. 同一笔支付可以多次部分退款
    """

    id: Optional[int]
    payment_id: int
    order_id: str  # 冗余，便于查询
    provider: str
    provider_refund_id: Optional[str]  # 渠道退款ID
    amount: Decimal
    currency: str
    status: RefundStatus
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    succeeded_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """初始化后验证"""
        if self.amount <= 0:
            raise DomainValidationException(
                f"退款金额必须大于0: {self.amount}",
                field="amount"
            )
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        self.succeeded_at = _ensure_utc(self.succeeded_at)
        self.failed_at = _ensure_utc(self.failed_at)
        if self.metadata is None:
            self.metadata = {}

    def mark_processing(self) -> None:
        """标记为处理中"""
        if self.status != RefundStatus.PENDING:
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 processing",
                field="status"
            )
        self.status = RefundStatus.PROCESSING
        self.updated_at = datetime.now(timezone.utc)

    def mark_succeeded(self, provider_refund_id: Optional[str] = None) -> None:
        """标记退款成功"""
        if self.status not in (RefundStatus.PENDING, RefundStatus.PROCESSING):
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 succeeded",
                field="status"
            )
        self.status = RefundStatus.SUCCEEDED
        if provider_refund_id:
            self.provider_refund_id = provider_refund_id
        self.succeeded_at = datetime.now(timezone.utc)
        self.updated_at = self.succeeded_at
        self.failure_reason = None

    def mark_failed(self, reason: Optional[str] = None) -> None:
        """标记退款失败"""
        if self.status not in (RefundStatus.PENDING, RefundStatus.PROCESSING):
            raise DomainValidationException(
                f"无法从状态 {self.status} 转换为 failed",
                field="status"
            )
        self.status = RefundStatus.FAILED
        self.failure_reason = reason
        self.failed_at = datetime.now(timezone.utc)
        self.updated_at = self.failed_at
