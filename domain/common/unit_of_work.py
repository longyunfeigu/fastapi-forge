"""Unit of Work 抽象定义"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.user.repository import UserRepository
from domain.file_asset.repository import FileAssetRepository


class AbstractUnitOfWork(ABC):
    """应用层事务边界控制抽象"""

    user_repository: UserRepository
    file_asset_repository: FileAssetRepository

    def __init__(self, *, readonly: bool = False) -> None:
        self._committed = False
        self._readonly = readonly
        self.user_repository = None  # type: ignore[assignment]
        self.file_asset_repository = None  # type: ignore[assignment]

    async def __aenter__(self) -> "AbstractUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.rollback()
        else:
            # 只在非只读且未显式提交时自动提交
            if not self._readonly and not self._committed:
                await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """提交事务"""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """回滚事务"""
