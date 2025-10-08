"""
支付仓储实现 - 使用SQLAlchemy实现数据访问
"""
from typing import Optional, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from domain.payment.entity import Payment, Refund, PaymentStatus, RefundStatus
from domain.payment.repository import PaymentRepository, RefundRepository
from domain.payment.service import PaymentAlreadyExistsException
from infrastructure.models.payment import PaymentModel, RefundModel
from core.logging_config import get_logger


logger = get_logger(__name__)


class SQLAlchemyPaymentRepository(PaymentRepository):
    """支付仓储的SQLAlchemy实现"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: PaymentModel) -> Payment:
        """将数据库模型转换为领域实体"""
        return Payment(
            id=model.id,
            order_id=model.order_id,
            user_id=model.user_id,
            provider=model.provider,
            provider_ref=model.provider_ref,
            amount=Decimal(str(model.amount)),
            currency=model.currency,
            status=PaymentStatus(model.status),
            scene=model.scene,
            refunded_amount=Decimal(str(model.refunded_amount)),
            refund_count=model.refund_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            paid_at=model.paid_at,
            canceled_at=model.canceled_at,
            notify_url=model.notify_url,
            return_url=model.return_url,
            client_secret=model.client_secret,
            failure_reason=model.failure_reason,
            metadata=model.extra_metadata or {}
        )

    def _to_model(self, entity: Payment) -> PaymentModel:
        """将领域实体转换为数据库模型"""
        return PaymentModel(
            id=entity.id,
            order_id=entity.order_id,
            user_id=entity.user_id,
            provider=entity.provider,
            provider_ref=entity.provider_ref,
            amount=entity.amount,
            currency=entity.currency,
            status=entity.status.value,
            scene=entity.scene,
            refunded_amount=entity.refunded_amount,
            refund_count=entity.refund_count,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            paid_at=entity.paid_at,
            canceled_at=entity.canceled_at,
            notify_url=entity.notify_url,
            return_url=entity.return_url,
            client_secret=entity.client_secret,
            failure_reason=entity.failure_reason,
            extra_metadata=entity.metadata
        )

    async def create(self, payment: Payment) -> Payment:
        """创建支付记录"""
        try:
            db_payment = self._to_model(payment)
            self.session.add(db_payment)
            await self.session.flush()
            await self.session.refresh(db_payment)
            logger.info(
                "payment_created",
                payment_id=db_payment.id,
                order_id=db_payment.order_id,
                provider=db_payment.provider
            )
            return self._to_entity(db_payment)
        except IntegrityError as e:
            await self.session.rollback()
            msg = str(e).lower()
            if "order_id" in msg:
                logger.warning(
                    "payment_create_conflict",
                    order_id=payment.order_id
                )
                raise PaymentAlreadyExistsException(payment.order_id)
            raise

    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        """根据ID获取支付"""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        db_payment = result.scalar_one_or_none()
        return self._to_entity(db_payment) if db_payment else None

    async def get_by_order_id(self, order_id: str) -> Optional[Payment]:
        """根据订单ID获取支付"""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.order_id == order_id)
        )
        db_payment = result.scalar_one_or_none()
        return self._to_entity(db_payment) if db_payment else None

    async def get_by_provider_ref(
        self,
        provider: str,
        provider_ref: str
    ) -> Optional[Payment]:
        """根据支付渠道引用ID获取支付"""
        result = await self.session.execute(
            select(PaymentModel).where(
                PaymentModel.provider == provider,
                PaymentModel.provider_ref == provider_ref
            )
        )
        db_payment = result.scalar_one_or_none()
        return self._to_entity(db_payment) if db_payment else None

    async def list_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[PaymentStatus] = None
    ) -> List[Payment]:
        """获取用户的支付列表"""
        query = select(PaymentModel).where(PaymentModel.user_id == user_id)

        if status:
            query = query.where(PaymentModel.status == status.value)

        query = query.order_by(PaymentModel.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        db_payments = result.scalars().all()
        return [self._to_entity(p) for p in db_payments]

    async def list_by_status(
        self,
        status: PaymentStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[Payment]:
        """根据状态获取支付列表"""
        result = await self.session.execute(
            select(PaymentModel)
            .where(PaymentModel.status == status.value)
            .order_by(PaymentModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        db_payments = result.scalars().all()
        return [self._to_entity(p) for p in db_payments]

    async def update(self, payment: Payment) -> Payment:
        """更新支付记录"""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment.id)
        )
        db_payment = result.scalar_one_or_none()

        if not db_payment:
            raise ValueError(f"Payment with id {payment.id} not found")

        # 更新字段
        db_payment.provider_ref = payment.provider_ref
        db_payment.status = payment.status.value
        db_payment.refunded_amount = payment.refunded_amount
        db_payment.refund_count = payment.refund_count
        db_payment.updated_at = payment.updated_at
        db_payment.paid_at = payment.paid_at
        db_payment.canceled_at = payment.canceled_at
        db_payment.client_secret = payment.client_secret
        db_payment.failure_reason = payment.failure_reason
        db_payment.extra_metadata = payment.metadata

        await self.session.flush()
        await self.session.refresh(db_payment)

        logger.info(
            "payment_updated",
            payment_id=db_payment.id,
            order_id=db_payment.order_id,
            status=db_payment.status
        )

        return self._to_entity(db_payment)

    async def delete(self, payment_id: int) -> bool:
        """删除支付记录"""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        db_payment = result.scalar_one_or_none()

        if not db_payment:
            return False

        await self.session.delete(db_payment)
        await self.session.flush()

        logger.info("payment_deleted", payment_id=payment_id)
        return True

    async def count_by_user(
        self,
        user_id: int,
        status: Optional[PaymentStatus] = None
    ) -> int:
        """统计用户的支付数量"""
        query = select(func.count(PaymentModel.id)).where(
            PaymentModel.user_id == user_id
        )

        if status:
            query = query.where(PaymentModel.status == status.value)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_total_amount_by_user(
        self,
        user_id: int,
        status: Optional[PaymentStatus] = None
    ) -> Decimal:
        """统计用户的支付总额"""
        query = select(func.sum(PaymentModel.amount)).where(
            PaymentModel.user_id == user_id
        )

        if status:
            query = query.where(PaymentModel.status == status.value)

        result = await self.session.execute(query)
        total = result.scalar_one_or_none()
        return Decimal(str(total)) if total else Decimal("0")

    async def exists_by_order_id(self, order_id: str) -> bool:
        """检查订单是否已有支付记录"""
        result = await self.session.execute(
            select(func.count(PaymentModel.id)).where(
                PaymentModel.order_id == order_id
            )
        )
        count = result.scalar_one()
        return count > 0


class SQLAlchemyRefundRepository(RefundRepository):
    """退款仓储的SQLAlchemy实现"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: RefundModel) -> Refund:
        """将数据库模型转换为领域实体"""
        return Refund(
            id=model.id,
            payment_id=model.payment_id,
            order_id=model.order_id,
            provider=model.provider,
            provider_refund_id=model.provider_refund_id,
            amount=Decimal(str(model.amount)),
            currency=model.currency,
            status=RefundStatus(model.status),
            reason=model.reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
            succeeded_at=model.succeeded_at,
            failed_at=model.failed_at,
            failure_reason=model.failure_reason,
            metadata=model.extra_metadata or {}
        )

    def _to_model(self, entity: Refund) -> RefundModel:
        """将领域实体转换为数据库模型"""
        return RefundModel(
            id=entity.id,
            payment_id=entity.payment_id,
            order_id=entity.order_id,
            provider=entity.provider,
            provider_refund_id=entity.provider_refund_id,
            amount=entity.amount,
            currency=entity.currency,
            status=entity.status.value,
            reason=entity.reason,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            succeeded_at=entity.succeeded_at,
            failed_at=entity.failed_at,
            failure_reason=entity.failure_reason,
            extra_metadata=entity.metadata
        )

    async def create(self, refund: Refund) -> Refund:
        """创建退款记录"""
        db_refund = self._to_model(refund)
        self.session.add(db_refund)
        await self.session.flush()
        await self.session.refresh(db_refund)

        logger.info(
            "refund_created",
            refund_id=db_refund.id,
            payment_id=db_refund.payment_id,
            order_id=db_refund.order_id,
            amount=str(db_refund.amount)
        )

        return self._to_entity(db_refund)

    async def get_by_id(self, refund_id: int) -> Optional[Refund]:
        """根据ID获取退款"""
        result = await self.session.execute(
            select(RefundModel).where(RefundModel.id == refund_id)
        )
        db_refund = result.scalar_one_or_none()
        return self._to_entity(db_refund) if db_refund else None

    async def get_by_provider_refund_id(
        self,
        provider: str,
        provider_refund_id: str
    ) -> Optional[Refund]:
        """根据渠道退款ID获取退款"""
        result = await self.session.execute(
            select(RefundModel).where(
                RefundModel.provider == provider,
                RefundModel.provider_refund_id == provider_refund_id
            )
        )
        db_refund = result.scalar_one_or_none()
        return self._to_entity(db_refund) if db_refund else None

    async def list_by_payment(
        self,
        payment_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Refund]:
        """获取支付的退款列表"""
        result = await self.session.execute(
            select(RefundModel)
            .where(RefundModel.payment_id == payment_id)
            .order_by(RefundModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        db_refunds = result.scalars().all()
        return [self._to_entity(r) for r in db_refunds]

    async def list_by_order_id(
        self,
        order_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Refund]:
        """根据订单ID获取退款列表"""
        result = await self.session.execute(
            select(RefundModel)
            .where(RefundModel.order_id == order_id)
            .order_by(RefundModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        db_refunds = result.scalars().all()
        return [self._to_entity(r) for r in db_refunds]

    async def update(self, refund: Refund) -> Refund:
        """更新退款记录"""
        result = await self.session.execute(
            select(RefundModel).where(RefundModel.id == refund.id)
        )
        db_refund = result.scalar_one_or_none()

        if not db_refund:
            raise ValueError(f"Refund with id {refund.id} not found")

        # 更新字段
        db_refund.provider_refund_id = refund.provider_refund_id
        db_refund.status = refund.status.value
        db_refund.updated_at = refund.updated_at
        db_refund.succeeded_at = refund.succeeded_at
        db_refund.failed_at = refund.failed_at
        db_refund.failure_reason = refund.failure_reason
        db_refund.extra_metadata = refund.metadata

        await self.session.flush()
        await self.session.refresh(db_refund)

        logger.info(
            "refund_updated",
            refund_id=db_refund.id,
            payment_id=db_refund.payment_id,
            status=db_refund.status
        )

        return self._to_entity(db_refund)

    async def count_by_payment(self, payment_id: int) -> int:
        """统计支付的退款次数"""
        result = await self.session.execute(
            select(func.count(RefundModel.id)).where(
                RefundModel.payment_id == payment_id
            )
        )
        return result.scalar_one()

    async def get_total_refunded_amount(self, payment_id: int) -> Decimal:
        """获取支付的退款总额"""
        result = await self.session.execute(
            select(func.sum(RefundModel.amount)).where(
                RefundModel.payment_id == payment_id,
                RefundModel.status == RefundStatus.SUCCEEDED.value
            )
        )
        total = result.scalar_one_or_none()
        return Decimal(str(total)) if total else Decimal("0")
