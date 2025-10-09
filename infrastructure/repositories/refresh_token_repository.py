"""
刷新令牌仓储实现 - 使用SQLAlchemy实现数据访问
"""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_

from domain.user.refresh_token_repository import RefreshTokenRepository
from infrastructure.models.refresh_token import RefreshTokenModel
from core.logging_config import get_logger


logger = get_logger(__name__)


class SQLAlchemyRefreshTokenRepository(RefreshTokenRepository):
    """刷新令牌仓储的SQLAlchemy实现"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        jti: str,
        user_id: int,
        family_id: str,
        parent_jti: Optional[str],
        token_hash: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> int:
        """创建刷新令牌记录"""
        db_token = RefreshTokenModel(
            jti=jti,
            user_id=user_id,
            family_id=family_id,
            parent_jti=parent_jti,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            is_revoked=False,
            is_used=False,
            created_at=datetime.now(timezone.utc)
        )

        self.session.add(db_token)
        await self.session.flush()
        await self.session.refresh(db_token)

        logger.info(
            "refresh_token_created",
            jti=jti,
            user_id=user_id,
            family_id=family_id
        )

        return db_token.id

    async def get_by_jti(self, jti: str) -> Optional[dict]:
        """根据JTI获取令牌记录"""
        result = await self.session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.jti == jti)
        )
        db_token = result.scalar_one_or_none()

        if not db_token:
            return None

        return {
            "id": db_token.id,
            "jti": db_token.jti,
            "user_id": db_token.user_id,
            "family_id": db_token.family_id,
            "parent_jti": db_token.parent_jti,
            "token_hash": db_token.token_hash,
            "is_revoked": db_token.is_revoked,
            "is_used": db_token.is_used,
            "expires_at": db_token.expires_at,
            "created_at": db_token.created_at,
            "device_info": db_token.device_info,
            "ip_address": db_token.ip_address,
        }

    async def mark_as_used(self, jti: str) -> bool:
        """标记令牌为已使用"""
        result = await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.jti == jti)
            .values(
                is_used=True,
                used_at=datetime.now(timezone.utc)
            )
        )

        if result.rowcount > 0:
            logger.info("refresh_token_marked_used", jti=jti)
            return True

        return False

    async def revoke_token(self, jti: str, reason: Optional[str] = None) -> bool:
        """撤销指定令牌"""
        result = await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.jti == jti)
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revoke_reason=reason
            )
        )

        if result.rowcount > 0:
            logger.warning("refresh_token_revoked", jti=jti, reason=reason)
            return True

        return False

    async def revoke_family(self, family_id: str, reason: Optional[str] = None) -> int:
        """撤销整个令牌家族

        为了避免部分驱动在 UPDATE rowcount 统计上的差异，这里先锁定目标行再更新，
        返回值以锁定行数为准，确保与业务感知一致。
        """
        # 1) 锁定目标行并收集ID（与当前事务一致性视图）
        ids_result = await self.session.execute(
            select(RefreshTokenModel.id)
            .where(
                and_(
                    RefreshTokenModel.family_id == family_id,
                    RefreshTokenModel.is_revoked == False,  # noqa: E712
                )
            )
            .with_for_update()
        )
        ids = [row[0] for row in ids_result.all()]
        if not ids:
            return 0

        # 2) 执行更新
        await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id.in_(ids))
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revoke_reason=reason or "Family revoked due to security breach",
            )
        )

        logger.warning(
            "refresh_token_family_revoked",
            family_id=family_id,
            count=len(ids),
            reason=reason,
        )
        return len(ids)

    async def revoke_all_user_tokens(self, user_id: int, reason: Optional[str] = None) -> int:
        """撤销用户所有令牌

        采用“先锁定并统计、再批量更新”的策略，避免某些 MySQL 驱动在 rowcount 语义上的差异
        造成返回 0 的困惑。
        """
        # 1) 锁定目标行并收集ID
        ids_result = await self.session.execute(
            select(RefreshTokenModel.id)
            .where(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.is_revoked == False,  # noqa: E712
                )
            )
            .with_for_update()
        )
        ids = [row[0] for row in ids_result.all()]
        if not ids:
            return 0

        # 2) 执行更新
        await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id.in_(ids))
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revoke_reason=reason or "User logout all devices",
            )
        )

        logger.info(
            "refresh_tokens_user_revoked",
            user_id=user_id,
            count=len(ids),
        )
        return len(ids)

    async def is_revoked(self, jti: str) -> bool:
        """检查令牌是否已撤销"""
        result = await self.session.execute(
            select(RefreshTokenModel.is_revoked)
            .where(RefreshTokenModel.jti == jti)
        )
        is_revoked = result.scalar_one_or_none()
        return bool(is_revoked) if is_revoked is not None else True

    async def is_used(self, jti: str) -> bool:
        """检查令牌是否已使用"""
        result = await self.session.execute(
            select(RefreshTokenModel.is_used)
            .where(RefreshTokenModel.jti == jti)
        )
        is_used = result.scalar_one_or_none()
        return bool(is_used) if is_used is not None else False

    async def cleanup_expired(self, before: datetime) -> int:
        """清理过期令牌"""
        # 删除已过期且已撤销或已使用的令牌
        result = await self.session.execute(
            select(RefreshTokenModel.id)
            .where(
                and_(
                    RefreshTokenModel.expires_at < before,
                    (RefreshTokenModel.is_revoked == True) |  # noqa: E712
                    (RefreshTokenModel.is_used == True)  # noqa: E712
                )
            )
        )
        expired_ids = [row[0] for row in result.all()]

        if expired_ids:
            # 批量删除
            from sqlalchemy import delete
            await self.session.execute(
                delete(RefreshTokenModel).where(
                    RefreshTokenModel.id.in_(expired_ids)
                )
            )
            logger.info("refresh_tokens_cleaned", count=len(expired_ids))
            return len(expired_ids)

        return 0

    async def get_active_tokens_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """获取用户的活跃令牌列表"""
        result = await self.session.execute(
            select(RefreshTokenModel)
            .where(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.is_revoked == False,  # noqa: E712
                    RefreshTokenModel.is_used == False,  # noqa: E712
                    RefreshTokenModel.expires_at > datetime.now(timezone.utc)
                )
            )
            .order_by(RefreshTokenModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        db_tokens = result.scalars().all()

        return [
            {
                "jti": token.jti,
                "family_id": token.family_id,
                "created_at": token.created_at,
                "expires_at": token.expires_at,
                "device_info": token.device_info,
                "ip_address": token.ip_address,
            }
            for token in db_tokens
        ]

    async def count_active_tokens_by_user(self, user_id: int) -> int:
        """统计用户的活跃令牌数量"""
        result = await self.session.execute(
            select(func.count(RefreshTokenModel.id))
            .where(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.is_revoked == False,  # noqa: E712
                    RefreshTokenModel.is_used == False,  # noqa: E712
                    RefreshTokenModel.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        return result.scalar_one()
