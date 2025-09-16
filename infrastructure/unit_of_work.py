"""SQLAlchemy Unit of Work 实现"""
from __future__ import annotations

from typing import Optional, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from domain.common.unit_of_work import AbstractUnitOfWork
from infrastructure.database import AsyncSessionLocal
from infrastructure.repositories.user_repository import SQLAlchemyUserRepository


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """基于SQLAlchemy的Unit of Work"""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
        session: Optional[AsyncSession] = None,
    ) -> None:
        super().__init__()
        self._session_factory = session_factory
        self._external_session = session
        self.session: Optional[AsyncSession] = session
        self.user_repository = None

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        if self.session is None:
            self.session = self._session_factory()
        self.user_repository = SQLAlchemyUserRepository(self.session)
        self._transaction = await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            if hasattr(self, "_transaction") and self._transaction.is_active:
                await self._transaction.close()
            if self._external_session is None and self.session is not None:
                await self.session.close()
                self.session = None

    async def commit(self) -> None:
        if self.session and self.session.in_transaction():
            await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self.session and self.session.in_transaction():
            await self.session.rollback()
        self._committed = False
