"""
用户领域服务 - 处理复杂的业务逻辑
"""
from typing import Optional, List
from datetime import datetime, timezone
import hashlib
import secrets

from .entity import User
from .repository import UserRepository
from .events import UserCreated, UserActivated, UserDeactivated, PasswordChanged


class PasswordService:
    """密码服务 - 处理密码相关的业务逻辑"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        # 实际项目中应使用 bcrypt 或 argon2
        salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', 
                                       password.encode('utf-8'), 
                                       salt.encode('utf-8'), 
                                       100000)
        return f"{salt}${pwd_hash.hex()}"
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            salt, pwd_hash = hashed_password.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256',
                                          plain_password.encode('utf-8'),
                                          salt.encode('utf-8'),
                                          100000)
            return new_hash.hex() == pwd_hash
        except:
            return False
    
    @staticmethod
    def validate_password_strength(password: str) -> None:
        """业务规则：密码强度验证"""
        if len(password) < 8:
            raise ValueError("密码长度至少8位")
        if not any(c.isupper() for c in password):
            raise ValueError("密码必须包含至少一个大写字母")
        if not any(c.islower() for c in password):
            raise ValueError("密码必须包含至少一个小写字母")
        if not any(c.isdigit() for c in password):
            raise ValueError("密码必须包含至少一个数字")


class UserDomainService:
    """用户领域服务 - 编排复杂的业务流程"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
        self.password_service = PasswordService()
        self.events: List = []  # 领域事件收集
    
    async def register_user(self, 
                           username: str,
                           email: str,
                           password: str,
                           full_name: Optional[str] = None,
                           phone: Optional[str] = None) -> User:
        """用户注册的业务流程"""
        # 业务规则1：验证密码强度
        self.password_service.validate_password_strength(password)
        
        # 业务规则2：检查用户名是否已存在
        if await self.user_repository.exists_by_username(username):
            raise ValueError(f"用户名 {username} 已被使用")
        
        # 业务规则3：检查邮箱是否已存在
        if await self.user_repository.exists_by_email(email):
            raise ValueError(f"邮箱 {email} 已被注册")
        
        # 业务规则4：创建用户实体
        hashed_password = self.password_service.hash_password(password)
        user = User(
            id=None,
            username=username,
            email=email,
            phone=phone,
            full_name=full_name,
            hashed_password=hashed_password,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # 业务规则5：首个用户设为超级管理员
        user_count = await self.user_repository.count_all()
        if user_count == 0:
            user.is_superuser = True
        
        # 保存用户
        created_user = await self.user_repository.create(user)
        
        # 发布领域事件
        self.events.append(UserCreated(user_id=created_user.id, 
                                       username=created_user.username,
                                       email=created_user.email))
        
        return created_user
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """用户认证的业务流程"""
        # 获取用户
        user = await self.user_repository.get_by_username(username)
        if not user:
            # 也可以通过邮箱登录
            user = await self.user_repository.get_by_email(username)
        
        if not user:
            return None
        
        # 验证密码
        if not self.password_service.verify_password(password, user.hashed_password):
            return None
        
        # 业务规则：检查用户是否激活
        if not user.is_active:
            raise ValueError("用户账户已被停用")
        
        # 记录登录时间
        user.record_login()
        await self.user_repository.update(user)
        
        return user
    
    async def change_user_password(self, user_id: int, 
                                  old_password: str, 
                                  new_password: str) -> User:
        """修改密码的业务流程"""
        # 获取用户
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 验证旧密码
        if not self.password_service.verify_password(old_password, user.hashed_password):
            raise ValueError("原密码错误")
        
        # 验证新密码强度
        self.password_service.validate_password_strength(new_password)
        
        # 业务规则：新密码不能与旧密码相同
        if old_password == new_password:
            raise ValueError("新密码不能与原密码相同")
        
        # 修改密码
        new_hash = self.password_service.hash_password(new_password)
        user.change_password(new_hash)
        
        # 保存更新
        updated_user = await self.user_repository.update(user)
        
        # 发布领域事件
        self.events.append(PasswordChanged(user_id=user_id))
        
        return updated_user
    
    async def activate_user(self, user_id: int) -> User:
        """激活用户"""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        user.activate()
        updated_user = await self.user_repository.update(user)
        
        # 发布领域事件
        self.events.append(UserActivated(user_id=user_id))
        
        return updated_user
    
    async def deactivate_user(self, user_id: int) -> User:
        """停用用户"""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        user.deactivate()
        updated_user = await self.user_repository.update(user)
        
        # 发布领域事件
        self.events.append(UserDeactivated(user_id=user_id))
        
        return updated_user
    
    def get_domain_events(self) -> List:
        """获取并清空领域事件"""
        events = self.events.copy()
        self.events.clear()
        return events
