"""
刷新令牌仓储接口 - 定义刷新令牌数据访问的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime


class RefreshTokenRepository(ABC):
    """刷新令牌仓储抽象接口"""

    @abstractmethod
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
        """
        创建刷新令牌记录

        Args:
            jti: JWT Token ID
            user_id: 用户ID
            family_id: 令牌家族ID
            parent_jti: 父令牌JTI
            token_hash: 令牌哈希
            expires_at: 过期时间
            device_info: 设备信息
            ip_address: IP地址

        Returns:
            创建的令牌ID
        """
        pass

    @abstractmethod
    async def get_by_jti(self, jti: str) -> Optional[dict]:
        """根据JTI获取令牌记录"""
        pass

    @abstractmethod
    async def mark_as_used(self, jti: str) -> bool:
        """标记令牌为已使用（轮转时调用）"""
        pass

    @abstractmethod
    async def revoke_token(self, jti: str, reason: Optional[str] = None) -> bool:
        """撤销指定令牌"""
        pass

    @abstractmethod
    async def revoke_family(self, family_id: str, reason: Optional[str] = None) -> int:
        """
        撤销整个令牌家族（检测到令牌重用时调用）

        Returns:
            撤销的令牌数量
        """
        pass

    @abstractmethod
    async def revoke_all_user_tokens(self, user_id: int, reason: Optional[str] = None) -> int:
        """
        撤销用户所有令牌（用户主动登出所有设备）

        Returns:
            撤销的令牌数量
        """
        pass

    @abstractmethod
    async def is_revoked(self, jti: str) -> bool:
        """检查令牌是否已撤销"""
        pass

    @abstractmethod
    async def is_used(self, jti: str) -> bool:
        """检查令牌是否已使用"""
        pass

    @abstractmethod
    async def cleanup_expired(self, before: datetime) -> int:
        """
        清理过期令牌

        Args:
            before: 清理此时间之前过期的令牌

        Returns:
            清理的令牌数量
        """
        pass

    @abstractmethod
    async def get_active_tokens_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """获取用户的活跃令牌列表（用于显示登录设备）"""
        pass

    @abstractmethod
    async def count_active_tokens_by_user(self, user_id: int) -> int:
        """统计用户的活跃令牌数量"""
        pass
