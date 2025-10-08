"""
支付领域服务 - 处理复杂的支付业务逻辑
"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timezone

from .entity import Payment, Refund, PaymentStatus, RefundStatus
from .repository import PaymentRepository, RefundRepository
from .events import PaymentSucceeded, PaymentFailed, PaymentRefunded, PaymentCanceled
from domain.common.exceptions import (
    DomainValidationException,
    BusinessException,
)


class PaymentAlreadyExistsException(BusinessException):
    """订单已存在支付记录"""
    def __init__(self, order_id: str):
        super().__init__(
            code=20100,
            message=f"订单 {order_id} 已存在支付记录",
            error_type="PAYMENT_ALREADY_EXISTS"
        )


class PaymentNotFoundException(BusinessException):
    """支付记录不存在"""
    def __init__(self, identifier: str):
        super().__init__(
            code=20101,
            message=f"支付记录不存在: {identifier}",
            error_type="PAYMENT_NOT_FOUND"
        )


class RefundExceedsPaymentException(BusinessException):
    """退款金额超过支付金额"""
    def __init__(self, refund_amount: Decimal, available: Decimal):
        super().__init__(
            code=20102,
            message=f"退款金额 {refund_amount} 超过可退金额 {available}",
            error_type="REFUND_EXCEEDS_PAYMENT"
        )


class PaymentNotRefundableException(BusinessException):
    """支付不可退款"""
    def __init__(self, status: PaymentStatus):
        super().__init__(
            code=20103,
            message=f"支付状态为 {status}，不可退款",
            error_type="PAYMENT_NOT_REFUNDABLE"
        )


class PaymentDomainService:
    """
    支付领域服务 - 编排复杂的业务流程

    职责：
    1. 创建支付时的业务校验（订单唯一性）
    2. 支付状态转换的业务规则
    3. 退款业务规则（金额校验、可退款判断）
    4. 产生领域事件
    """

    def __init__(
        self,
        payment_repository: PaymentRepository,
        refund_repository: RefundRepository
    ):
        self.payment_repository = payment_repository
        self.refund_repository = refund_repository
        self.events: List = []  # 领域事件收集

    async def create_payment(
        self,
        order_id: str,
        user_id: Optional[int],
        provider: str,
        amount: Decimal,
        currency: str,
        scene: str,
        notify_url: Optional[str] = None,
        return_url: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Payment:
        """
        创建支付记录

        业务规则：
        1. 订单ID不能重复
        2. 金额必须大于0
        3. 货币代码必须有效
        """
        # 业务规则：检查订单是否已有支付
        if await self.payment_repository.exists_by_order_id(order_id):
            raise PaymentAlreadyExistsException(order_id)

        # 创建支付实体（实体内部会进行验证）
        payment = Payment(
            id=None,
            order_id=order_id,
            user_id=user_id,
            provider=provider,
            provider_ref=None,
            amount=amount,
            currency=currency.upper(),
            status=PaymentStatus.PENDING,
            scene=scene,
            refunded_amount=Decimal("0"),
            refund_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            notify_url=notify_url,
            return_url=return_url,
            metadata=metadata or {}
        )

        # 持久化
        created = await self.payment_repository.create(payment)
        return created

    async def confirm_payment_success(
        self,
        payment_id: int,
        provider_ref: Optional[str] = None
    ) -> Payment:
        """
        确认支付成功

        业务规则：
        1. 支付必须存在
        2. 状态必须允许转为成功
        """
        payment = await self.payment_repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"id={payment_id}")

        # 实体方法处理状态转换
        payment.mark_succeeded(provider_ref)

        # 持久化
        updated = await self.payment_repository.update(payment)

        # 记录领域事件
        self.events.append(PaymentSucceeded(
            order_id=updated.order_id,
            provider=updated.provider,
            provider_ref=updated.provider_ref
        ))

        return updated

    async def mark_payment_failed(
        self,
        payment_id: int,
        reason: Optional[str] = None
    ) -> Payment:
        """标记支付失败"""
        payment = await self.payment_repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"id={payment_id}")

        payment.mark_failed(reason)
        updated = await self.payment_repository.update(payment)

        # 记录领域事件
        self.events.append(PaymentFailed(
            order_id=updated.order_id,
            provider=updated.provider,
            provider_ref=updated.provider_ref,
            reason=reason
        ))

        return updated

    async def cancel_payment(self, payment_id: int) -> Payment:
        """取消支付"""
        payment = await self.payment_repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"id={payment_id}")

        payment.mark_canceled()
        updated = await self.payment_repository.update(payment)

        # 记录领域事件
        self.events.append(PaymentCanceled(
            order_id=updated.order_id,
            provider=updated.provider,
            provider_ref=updated.provider_ref
        ))

        return updated

    async def create_refund(
        self,
        payment_id: int,
        amount: Decimal,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> tuple[Payment, Refund]:
        """
        创建退款

        业务规则：
        1. 支付必须存在且状态为成功或部分退款
        2. 退款金额不能超过剩余可退金额
        3. 退款成功后更新支付的退款金额和状态

        返回：(更新后的Payment, 新创建的Refund)
        """
        payment = await self.payment_repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"id={payment_id}")

        # 业务规则：检查是否可以退款
        if not payment.can_refund():
            raise PaymentNotRefundableException(payment.status)

        # 业务规则：检查退款金额
        refundable = payment.calculate_refundable_amount()
        if amount > refundable:
            raise RefundExceedsPaymentException(amount, refundable)

        # 创建退款实体
        refund = Refund(
            id=None,
            payment_id=payment_id,
            order_id=payment.order_id,
            provider=payment.provider,
            provider_refund_id=None,
            amount=amount,
            currency=payment.currency,
            status=RefundStatus.PENDING,
            reason=reason,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata=metadata or {}
        )

        # 持久化退款
        created_refund = await self.refund_repository.create(refund)

        # 更新支付（应用退款）
        payment.apply_refund(amount)
        updated_payment = await self.payment_repository.update(payment)

        return updated_payment, created_refund

    async def confirm_refund_success(
        self,
        refund_id: int,
        provider_refund_id: Optional[str] = None
    ) -> Refund:
        """确认退款成功"""
        refund = await self.refund_repository.get_by_id(refund_id)
        if not refund:
            raise BusinessException(
                code=20104,
                message=f"退款记录不存在: id={refund_id}",
                error_type="REFUND_NOT_FOUND"
            )

        refund.mark_succeeded(provider_refund_id)
        updated = await self.refund_repository.update(refund)

        # 记录领域事件
        self.events.append(PaymentRefunded(
            order_id=refund.order_id,
            provider=refund.provider,
            provider_ref=provider_refund_id,
            refund_id=str(refund.id) if refund.id else "",
            amount=str(refund.amount)
        ))

        return updated

    async def mark_refund_failed(
        self,
        refund_id: int,
        reason: Optional[str] = None
    ) -> tuple[Refund, Payment]:
        """
        标记退款失败

        业务规则：退款失败需要回滚支付的退款金额
        """
        refund = await self.refund_repository.get_by_id(refund_id)
        if not refund:
            raise BusinessException(
                code=20104,
                message=f"退款记录不存在: id={refund_id}",
                error_type="REFUND_NOT_FOUND"
            )

        # 获取关联的支付
        payment = await self.payment_repository.get_by_id(refund.payment_id)
        if not payment:
            raise PaymentNotFoundException(f"id={refund.payment_id}")

        # 标记退款失败
        refund.mark_failed(reason)
        updated_refund = await self.refund_repository.update(refund)

        # 回滚支付的退款金额（因为退款失败了）
        payment.refunded_amount -= refund.amount
        payment.refund_count -= 1
        payment.updated_at = datetime.now(timezone.utc)

        # 重新计算支付状态
        if payment.refunded_amount == 0:
            payment.status = PaymentStatus.SUCCEEDED
        elif payment.refunded_amount < payment.amount:
            payment.status = PaymentStatus.PARTIAL_REFUNDED

        updated_payment = await self.payment_repository.update(payment)

        return updated_refund, updated_payment

    def clear_events(self) -> List:
        """清空并返回领域事件"""
        events = self.events.copy()
        self.events.clear()
        return events
