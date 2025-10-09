"""
令牌服务 - 处理JWT令牌和刷新令牌轮转逻辑
"""
from typing import Optional, Callable
from datetime import datetime, timedelta, timezone
import jwt
import uuid
import hashlib

from domain.user.entity import User
from domain.common.unit_of_work import AbstractUnitOfWork
from application.dto import TokenDTO
from core.config import settings
from domain.common.exceptions import UserNotFoundException, UserInactiveException
from core.exceptions import UnauthorizedException, TokenExpiredException
from core.logging_config import get_logger


logger = get_logger(__name__)


class TokenService:
    """
    令牌服务 - 实现刷新令牌轮转（Refresh Token Rotation）

    安全特性：
    1. 每次使用刷新令牌时，旧令牌立即失效，生成新令牌
    2. 检测令牌重用：如果已使用的令牌再次被使用，撤销整个令牌家族
    3. 令牌存储哈希而非明文
    4. 支持令牌撤销（用户登出）
    5. 追踪令牌家族链
    """

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork]):
        self._uow_factory = uow_factory

    def _hash_token(self, token: str) -> str:
        """计算令牌的SHA-256哈希"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_jti(self) -> str:
        """生成唯一的JWT Token ID"""
        return str(uuid.uuid4())

    def _generate_family_id(self) -> str:
        """生成令牌家族ID（同一登录会话共享）"""
        return str(uuid.uuid4())

    def create_access_token(self, user: User) -> str:
        """创建访问令牌"""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode = {
            "sub": str(user.id),
            "username": user.username,
            "is_superuser": user.is_superuser,
            "exp": expire,
            "type": "access",
            "jti": self._generate_jti(),  # 添加JTI用于追踪
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def create_refresh_token(
        self,
        user: User,
        family_id: Optional[str] = None,
        parent_jti: Optional[str] = None,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        *,
        uow: Optional[AbstractUnitOfWork] = None,
    ) -> str:
        """
        创建刷新令牌并存储到数据库

        Args:
            user: 用户实体
            family_id: 令牌家族ID（轮转时传入）
            parent_jti: 父令牌JTI（轮转时传入）
            device_info: 设备信息
            ip_address: IP地址

        Returns:
            刷新令牌字符串
        """
        jti = self._generate_jti()
        if family_id is None:
            family_id = self._generate_family_id()

        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        to_encode = {
            "sub": str(user.id),
            "username": user.username,
            "exp": expire,
            "type": "refresh",
            "jti": jti,
            "family_id": family_id,
        }

        token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        token_hash = self._hash_token(token)

        # 存储到数据库
        if uow is None:
            async with self._uow_factory() as uow_local:
                await uow_local.refresh_token_repository.create(
                    jti=jti,
                    user_id=user.id,
                    family_id=family_id,
                    parent_jti=parent_jti,
                    token_hash=token_hash,
                    expires_at=expire,
                    device_info=device_info,
                    ip_address=ip_address,
                )
        else:
            await uow.refresh_token_repository.create(
                jti=jti,
                user_id=user.id,
                family_id=family_id,
                parent_jti=parent_jti,
                token_hash=token_hash,
                expires_at=expire,
                device_info=device_info,
                ip_address=ip_address,
            )

        logger.info(
            "refresh_token_created",
            user_id=user.id,
            jti=jti,
            family_id=family_id
        )

        return token

    async def rotate_refresh_token(
        self,
        refresh_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> TokenDTO:
        """
        刷新令牌轮转 - 核心安全逻辑

        流程：
        1. 验证令牌签名和过期时间
        2. 检查令牌是否已被撤销
        3. 检查令牌是否已被使用（检测重用攻击）
        4. 标记旧令牌为已使用
        5. 生成新的访问令牌和刷新令牌
        6. 返回新令牌对

        安全机制：
        - 如果检测到已使用的令牌被再次使用，撤销整个令牌家族
        """
        # 1. 解码并验证令牌
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException()
        except jwt.PyJWTError as e:
            logger.warning("invalid_refresh_token", error=str(e))
            raise UnauthorizedException("无效的刷新令牌")

        if payload.get("type") != "refresh":
            raise UnauthorizedException("令牌类型错误")

        jti = payload.get("jti")
        family_id = payload.get("family_id")
        user_id = payload.get("sub")

        if not all([jti, family_id, user_id]):
            raise UnauthorizedException("令牌缺少必要字段")

        async with self._uow_factory() as uow:
            # 2. 检查令牌是否存在于数据库
            token_record = await uow.refresh_token_repository.get_by_jti(jti)

            if not token_record:
                logger.warning("refresh_token_not_found", jti=jti)
                raise UnauthorizedException("令牌不存在")

            # 3. 验证令牌哈希
            token_hash = self._hash_token(refresh_token)
            if token_hash != token_record["token_hash"]:
                logger.error("refresh_token_hash_mismatch", jti=jti)
                raise UnauthorizedException("令牌哈希不匹配")

            # 4. 检查令牌是否已撤销
            if token_record["is_revoked"]:
                logger.warning("refresh_token_already_revoked", jti=jti, family_id=family_id)
                raise UnauthorizedException("令牌已被撤销")

            # 5. 检测令牌重用攻击
            if token_record["is_used"]:
                logger.error(
                    "refresh_token_reuse_detected",
                    jti=jti,
                    family_id=family_id,
                    user_id=user_id
                )
                # 撤销整个令牌家族（安全措施）
                revoked_count = await uow.refresh_token_repository.revoke_family(
                    family_id,
                    reason="Token reuse detected"
                )
                logger.error(
                    "refresh_token_family_revoked",
                    family_id=family_id,
                    revoked_count=revoked_count
                )
                raise UnauthorizedException("检测到令牌重用，已撤销所有相关令牌")

            # 6. 获取用户信息
            user = await uow.user_repository.get_by_id(int(user_id))
            if not user:
                raise UserNotFoundException(str(user_id))
            if not user.is_active:
                raise UserInactiveException()

            # 7. 标记旧令牌为已使用
            await uow.refresh_token_repository.mark_as_used(jti)

            # 8. 生成新令牌对（使用相同的 family_id，记录 parent_jti）
            new_access_token = self.create_access_token(user)
            # 重要：在同一事务内生成并持久化新的刷新令牌，避免外键检查时与其他事务互相等待
            new_refresh_token = await self.create_refresh_token(
                user,
                family_id=family_id,
                parent_jti=jti,
                device_info=device_info,
                ip_address=ip_address,
                uow=uow,
            )

            logger.info(
                "refresh_token_rotated",
                user_id=user.id,
                old_jti=jti,
                family_id=family_id
            )

            return TokenDTO(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )

    async def verify_access_token(self, token: str) -> Optional[int]:
        """Verify an access JWT and return the user id.

        Semantics are aligned with existing application expectations:
        - Expired token: raise TokenExpiredException
        - Invalid token or wrong type: return None
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException()
        except jwt.InvalidTokenError:
            return None

        if payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)

    async def revoke_token(self, jti: str, reason: Optional[str] = None) -> bool:
        """撤销单个刷新令牌"""
        async with self._uow_factory() as uow:
            success = await uow.refresh_token_repository.revoke_token(jti, reason)
            if success:
                logger.info("refresh_token_revoked_manual", jti=jti, reason=reason)
            return success

    async def revoke_all_user_tokens(self, user_id: int, reason: Optional[str] = None) -> int:
        """撤销用户所有刷新令牌（登出所有设备）"""
        async with self._uow_factory() as uow:
            count = await uow.refresh_token_repository.revoke_all_user_tokens(
                user_id,
                reason or "User logout all devices"
            )
            logger.info("user_tokens_revoked", user_id=user_id, count=count)
            return count

    async def get_active_sessions(self, user_id: int) -> list:
        """获取用户的活跃会话列表"""
        async with self._uow_factory(readonly=True) as uow:
            tokens = await uow.refresh_token_repository.get_active_tokens_by_user(user_id)
            # 按家族ID分组，每个家族只显示最新的令牌
            families = {}
            for token in tokens:
                family_id = token["family_id"]
                if family_id not in families:
                    families[family_id] = token
                elif token["created_at"] > families[family_id]["created_at"]:
                    families[family_id] = token

            return list(families.values())

    async def cleanup_expired_tokens(self, days_before: int = 30) -> int:
        """清理过期的刷新令牌"""
        before = datetime.now(timezone.utc) - timedelta(days=days_before)
        async with self._uow_factory() as uow:
            count = await uow.refresh_token_repository.cleanup_expired(before)
            logger.info("expired_tokens_cleaned", count=count)
            return count
