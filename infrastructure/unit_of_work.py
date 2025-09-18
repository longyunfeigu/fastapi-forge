"""SQLAlchemy Unit of Work 实现"""
from __future__ import annotations

from typing import Optional, Callable
import inspect

from sqlalchemy.ext.asyncio import AsyncSession

from domain.common.unit_of_work import AbstractUnitOfWork
from infrastructure.database import AsyncSessionLocal
from infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from infrastructure.repositories.file_asset_repository import (
    SQLAlchemyFileAssetRepository,
)


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """基于SQLAlchemy的Unit of Work"""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
        session: Optional[AsyncSession] = None,
        *,
        readonly: bool = False,
    ) -> None:
        super().__init__(readonly=readonly)
        self._session_factory = session_factory
        self._external_session = session
        self.session: Optional[AsyncSession] = session
        self.user_repository = None
        self.file_asset_repository = None

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        if self.session is None:
            self.session = self._session_factory()
        self.user_repository = SQLAlchemyUserRepository(self.session)
        self.file_asset_repository = SQLAlchemyFileAssetRepository(self.session)
        # 仅在非只读模式下显式开启事务
        if not self._readonly:
            self._transaction = await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            # 事务在 commit/rollback 后通常会结束，这里仅在仍然活动时做安全关闭
            tx = getattr(self, "_transaction", None)
            if tx is not None and getattr(tx, "is_active", False):
                close = getattr(tx, "close", None)
                if callable(close):
                    res = close()
                    if inspect.isawaitable(res):
                        await res
            if self._external_session is None and self.session is not None:
                await self.session.close()
                self.session = None
            self.user_repository = None
            self.file_asset_repository = None

    async def commit(self) -> None:
        if self._readonly:
            # 只读情况下不提交
            self._committed = True
            return
        if self.session and self.session.in_transaction():
            await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self.session and self.session.in_transaction():
            await self.session.rollback()
        self._committed = False
