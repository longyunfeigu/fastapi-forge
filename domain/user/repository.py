"""
用户仓储接口 - 定义数据访问的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from .entity import User


class UserRepository(ABC):
    """用户仓储抽象接口 - 只定义能做什么，不管怎么做"""
    
    @abstractmethod
    async def create(self, user: User) -> User:
        """创建用户"""
        pass
    
    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        pass
    
    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        pass
    
    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100, 
                      is_active: Optional[bool] = None) -> List[User]:
        """获取用户列表"""
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """更新用户"""
        pass
    
    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        """删除用户"""
        pass
    
    @abstractmethod
    async def exists_by_username(self, username: str) -> bool:
        """检查用户名是否存在"""
        pass
    
    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """检查邮箱是否存在"""
        pass
    
    @abstractmethod
    async def count_all(self, is_active: Optional[bool] = None) -> int:
        """统计用户数量"""
        pass