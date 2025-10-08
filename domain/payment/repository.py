"""
支付仓储接口 - 定义支付数据访问的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from decimal import Decimal

from .entity import Payment, Refund, PaymentStatus


class PaymentRepository(ABC):
    """支付仓储抽象接口 - 只定义能做什么，不管怎么做"""

    @abstractmethod
    async def create(self, payment: Payment) -> Payment:
        """创建支付记录"""
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        """根据ID获取支付"""
        pass

    @abstractmethod
    async def get_by_order_id(self, order_id: str) -> Optional[Payment]:
        """根据订单ID获取支付（假设一个订单一笔支付）"""
        pass

    @abstractmethod
    async def get_by_provider_ref(self, provider: str, provider_ref: str) -> Optional[Payment]:
        """根据支付渠道引用ID获取支付"""
        pass

    @abstractmethod
    async def list_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[PaymentStatus] = None
    ) -> List[Payment]:
        """获取用户的支付列表"""
        pass

    @abstractmethod
    async def list_by_status(
        self,
        status: PaymentStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[Payment]:
        """根据状态获取支付列表"""
        pass

    @abstractmethod
    async def update(self, payment: Payment) -> Payment:
        """更新支付记录"""
        pass

    @abstractmethod
    async def delete(self, payment_id: int) -> bool:
        """删除支付记录（软删除或硬删除由实现决定）"""
        pass

    @abstractmethod
    async def count_by_user(
        self,
        user_id: int,
        status: Optional[PaymentStatus] = None
    ) -> int:
        """统计用户的支付数量"""
        pass

    @abstractmethod
    async def get_total_amount_by_user(
        self,
        user_id: int,
        status: Optional[PaymentStatus] = None
    ) -> Decimal:
        """统计用户的支付总额"""
        pass

    @abstractmethod
    async def exists_by_order_id(self, order_id: str) -> bool:
        """检查订单是否已有支付记录"""
        pass


class RefundRepository(ABC):
    """退款仓储抽象接口"""

    @abstractmethod
    async def create(self, refund: Refund) -> Refund:
        """创建退款记录"""
        pass

    @abstractmethod
    async def get_by_id(self, refund_id: int) -> Optional[Refund]:
        """根据ID获取退款"""
        pass

    @abstractmethod
    async def get_by_provider_refund_id(
        self,
        provider: str,
        provider_refund_id: str
    ) -> Optional[Refund]:
        """根据渠道退款ID获取退款"""
        pass

    @abstractmethod
    async def list_by_payment(
        self,
        payment_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Refund]:
        """获取支付的退款列表"""
        pass

    @abstractmethod
    async def list_by_order_id(
        self,
        order_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Refund]:
        """根据订单ID获取退款列表"""
        pass

    @abstractmethod
    async def update(self, refund: Refund) -> Refund:
        """更新退款记录"""
        pass

    @abstractmethod
    async def count_by_payment(self, payment_id: int) -> int:
        """统计支付的退款次数"""
        pass

    @abstractmethod
    async def get_total_refunded_amount(self, payment_id: int) -> Decimal:
        """获取支付的退款总额"""
        pass
