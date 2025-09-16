"""Unit of Work 抽象定义"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.user.repository import UserRepository


class AbstractUnitOfWork(ABC):
    """应用层事务边界控制抽象"""

    user_repository: UserRepository

    def __init__(self) -> None:
        self._committed = False

    async def __aenter__(self) -> "AbstractUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.rollback()
        elif not self._committed:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """提交事务"""
        self._committed = True

    @abstractmethod
    async def rollback(self) -> None:
        """回滚事务"""
