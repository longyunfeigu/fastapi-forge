"""
API依赖项 - 认证和授权
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from application.user_service import UserApplicationService
from application.file_asset_service import FileAssetApplicationService
from application.ports.storage import StoragePort
from application.dto import UserResponseDTO
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from infrastructure.external.storage import get_storage
from infrastructure.adapters.storage_port import StorageProviderPortAdapter

# OAuth2 password bearer for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/login",
    scheme_name="OAuth2",
    description="Login with username and password to get token",
    auto_error=False,
)

# HTTP Bearer for direct API calls
http_bearer = HTTPBearer(
    scheme_name="Bearer",
    description="JWT Bearer token authentication",
    auto_error=False,
)


async def get_token(
    oauth2_token: Optional[str] = Depends(oauth2_scheme),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> str:
    """从OAuth2或Bearer token中提取token"""
    # 优先使用OAuth2 token (from Swagger UI)
    if oauth2_token:
        return oauth2_token
    
    # 然后尝试Bearer token (from direct API calls)
    if bearer_token and bearer_token.credentials:
        return bearer_token.credentials
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未提供认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_user_service() -> UserApplicationService:
    return UserApplicationService(uow_factory=SQLAlchemyUnitOfWork)


async def get_storage_port(provider = Depends(get_storage)) -> StoragePort:
    return StorageProviderPortAdapter(provider)


async def get_file_asset_service(storage: StoragePort = Depends(get_storage_port)) -> FileAssetApplicationService:
    # Inject storage port adapter (implements application port)
    return FileAssetApplicationService(uow_factory=SQLAlchemyUnitOfWork, storage=storage)


async def get_current_user(
    token: str = Depends(get_token),
    service: UserApplicationService = Depends(get_user_service)
) -> UserResponseDTO:
    """获取当前登录用户"""
    user_id = await service.verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await service.get_user(user_id)


async def get_current_active_user(
    current_user: UserResponseDTO = Depends(get_current_user)
) -> UserResponseDTO:
    """获取当前激活的用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被停用"
        )
    return current_user


async def get_current_superuser(
    current_user: UserResponseDTO = Depends(get_current_active_user)
) -> UserResponseDTO:
    """获取当前超级管理员用户"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user
